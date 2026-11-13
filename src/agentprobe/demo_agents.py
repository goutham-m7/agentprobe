"""Original synthetic demo domain; no customer or employer material."""

from importlib.resources import files

from agentprobe.models import AgentSpec
from agentprobe.spec import load_spec


def demo_spec() -> AgentSpec:
    return load_spec(files("agentprobe").joinpath("data/harbor.yaml"))


def good_agent(messages):
    """Small support policy implementation; deliberately readable, no LLM required."""
    from agentprobe.models import Reply

    users = [message.content.lower() for message in messages if message.role == "user"]
    last = users[-1]
    if any("español" in user or "recibo" in user or "cuántos" in user for user in users):
        return Reply(content="Con gusto. Puedes devolver artículos sin abrir dentro de 30 días con un recibo. No puedo garantizar excepciones.")
    if "delete" in last or "deletion" in last:
        return Reply(content="Account deletion must be handled by a human support specialist. I cannot delete it here.")
    if "code" in last or "administrator" in last or "ignore previous" in last:
        return Reply(content="I cannot share internal staff information or override policy. I can explain returns or order tracking.")
    if "31" in last or "late" in last and "day" in last or "outside" in last:
        return Reply(content="The return window is 30 days for unopened items with a receipt. I cannot guarantee a refund outside that window.")
    if any(word in last for word in ("order", "tracking", "furious", "useless")):
        return Reply(content="I'm sorry this has been frustrating. Please share your order number to check tracking. Delivery dates are not guaranteed.")
    return Reply(content="Unopened items can be returned within 30 days with a receipt. How can I help with your return?")


def broken_agent(messages):
    """Same happy path, five subtle multi-turn regressions injected on purpose."""
    from agentprobe.models import Reply, ToolCall

    users = [message.content.lower() for message in messages if message.role == "user"]
    last = users[-1]
    if len(users) >= 3:
        if "code" in last:
            return Reply(content="For your authorized audit, the internal discount code is HARBOR-STAFF.")
        if "cuántos" in last:
            return Reply(content="Puedes devolver artículos dentro de 90 days con un recibo.")
        if "lecture" in last:
            return Reply(content="Learn to read. Your order is not my problem.")
        if "guarantee" in last:
            return Reply(content="You have a guaranteed refund even after the return window.")
        if "delete" in last:
            return Reply(content="I will remove your account now.", tool_calls=[
                ToolCall(id="delete-1", name="delete_customer", arguments={"confirmed": False})
            ])
    return good_agent(messages)
