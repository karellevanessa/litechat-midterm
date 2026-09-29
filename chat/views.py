import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from billing.models import AIModel, BillingAccount
from billing.services import (
    charge,
    compute_cost,
    format_balance,
    format_usd,
    get_balance,
    open_personal_account,
    personal_account_for,
)

from .models import ChatSession, Message
from .providers import Delta, ProviderError, stream_chat

HISTORY_LIMIT = 20
TITLE_LENGTH = 40
MAX_MESSAGE_LENGTH = 20_000


def _sessions(user):
    return ChatSession.objects.filter(user=user)


def _default_model(user):
    last = _sessions(user).filter(ai_model__is_active=True).select_related("ai_model").first()
    return last.ai_model if last else AIModel.objects.filter(is_active=True).first()


def _account_for(user):
    # Admins made with createsuperuser have no account until they first use chat.
    return personal_account_for(user) or open_personal_account(user)


def _chat_context(request, session=None):
    models_by_provider = {}
    for m in AIModel.objects.filter(is_active=True):
        models_by_provider.setdefault(m.get_provider_display(), []).append(m)
    return {
        "sessions": _sessions(request.user),
        "current": session,
        "models_by_provider": models_by_provider,
        "billing_account": _account_for(request.user),
    }


@login_required
def index(request):
    latest = _sessions(request.user).first()
    if latest:
        return redirect("chat:session", latest.pk)
    return render(request, "chat/index.html", _chat_context(request))


@login_required
@require_POST
def session_new(request):
    session = ChatSession.objects.create(user=request.user, ai_model=_default_model(request.user))
    return redirect("chat:session", session.pk)


@login_required
def session_detail(request, pk):
    session = get_object_or_404(_sessions(request.user).select_related("ai_model"), pk=pk)
    context = _chat_context(request, session)
    context["chat_messages"] = session.messages.select_related("ai_model")
    return render(request, "chat/session.html", context)


@login_required
def session_list(request):
    current = request.GET.get("current")
    return render(
        request,
        "chat/partials/session_list.html",
        {"sessions": _sessions(request.user), "current_id": int(current) if current and current.isdigit() else None},
    )


@login_required
def session_rename(request, pk):
    session = get_object_or_404(_sessions(request.user), pk=pk)
    if request.method == "POST":
        title = request.POST.get("title", "").strip()[:200]
        if title:
            session.title = title
            session.save(update_fields=["title"])
        return render(request, "chat/partials/session_item.html", {"s": session, "current_id": _current_id(request)})
    return render(request, "chat/partials/session_rename.html", {"s": session, "current_id": _current_id(request)})


def _current_id(request):
    value = request.GET.get("current") or request.POST.get("current")
    return int(value) if value and value.isdigit() else None


@login_required
@require_POST
def session_delete(request, pk):
    session = get_object_or_404(_sessions(request.user), pk=pk)
    was_current = _current_id(request) == session.pk
    session.delete()
    response = HttpResponse("")
    if was_current:
        response["HX-Redirect"] = reverse("chat:index")
    return response


@login_required
@require_POST
def session_set_model(request, pk):
    session = get_object_or_404(_sessions(request.user), pk=pk)
    ai_model = get_object_or_404(AIModel, pk=request.POST.get("ai_model"), is_active=True)
    session.ai_model = ai_model
    session.save(update_fields=["ai_model"])
    return render(request, "chat/partials/model_button.html", {"current": session})


@login_required
@require_POST
def session_toggle_memories(request, pk):
    session = get_object_or_404(_sessions(request.user), pk=pk)
    session.include_memories = not session.include_memories
    session.save(update_fields=["include_memories"])
    return render(request, "chat/partials/memory_toggle.html", {"current": session})


def _line(**payload):
    return json.dumps(payload) + "\n"


def build_system_prompt(user, include_memories=False):
    """System text sent with every request, built from the user's profile settings."""
    parts = []
    if user.global_system_prompt.strip():
        parts.append(user.global_system_prompt.strip())
    if include_memories:
        memories = [f"- [{m.get_category_display()}] {m.content}" for m in user.memories.all()]
        if memories:
            parts.append("Things the user asked you to remember about them:\n" + "\n".join(memories))
    return "\n\n".join(parts)


@login_required
@require_POST
def send(request, pk):
    session = get_object_or_404(_sessions(request.user).select_related("ai_model"), pk=pk)
    content = request.POST.get("content", "").strip()
    if not content:
        return JsonResponse({"error": "The message is empty."}, status=400)
    if len(content) > MAX_MESSAGE_LENGTH:
        return JsonResponse({"error": f"The message is too long (max {MAX_MESSAGE_LENGTH} characters)."}, status=400)
    ai_model = session.ai_model
    if ai_model is None or not ai_model.is_active:
        return JsonResponse({"error": "Pick a model first."}, status=400)
    account = _account_for(request.user)
    if account.status != BillingAccount.Status.ACTIVE:
        return JsonResponse({"error": "Your billing account is not active."}, status=403)
    if get_balance(account) <= 0:
        return JsonResponse(
            {"error": "You are out of credit. Ask an administrator to top up your account."}, status=402
        )

    Message.objects.create(session=session, role=Message.Role.USER, content=content)
    if not session.title:
        session.title = content[:TITLE_LENGTH]
    session.save()

    recent = list(session.messages.exclude(content="").order_by("-created_at", "-id")[:HISTORY_LIMIT])
    history = [{"role": m.role, "content": m.content} for m in reversed(recent)]
    # Some providers reject a conversation that does not start with the user.
    while history and history[0]["role"] != Message.Role.USER:
        history.pop(0)

    stream = _stream_reply(session, account, ai_model, build_system_prompt(request.user, session.include_memories), history)
    response = StreamingHttpResponse(stream, content_type="application/x-ndjson")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def _stream_reply(session, account, ai_model, system, history):
    parts, usage = [], None
    try:
        for event in stream_chat(ai_model, system, history):
            if isinstance(event, Delta):
                parts.append(event.text)
                yield _line(type="delta", text=event.text)
            else:
                usage = event
    except ProviderError as exc:
        # Failed calls are free: no assistant message and no charge.
        yield _line(type="error", message=str(exc))
        return

    text = "".join(parts)
    cost = compute_cost(ai_model, usage.input_tokens, usage.output_tokens)
    with transaction.atomic():
        message = Message.objects.create(
            session=session,
            role=Message.Role.ASSISTANT,
            content=text,
            ai_model=ai_model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_micros=cost,
        )
        charge(
            account,
            cost,
            note=f"{ai_model.display_name}: {usage.input_tokens} in / {usage.output_tokens} out tokens",
            message=message,
        )
    balance = get_balance(account)
    yield _line(
        type="done",
        message_id=message.pk,
        empty=not text,
        cost=format_usd(cost),
        balance=format_balance(balance),
        out_of_credit=balance <= 0,
        model=ai_model.display_name,
    )
