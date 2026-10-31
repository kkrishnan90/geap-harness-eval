"""Original acknowledgement mode ACK generation."""

from .message import Message, Segment

ACCEPT, ERROR, REJECT = "AA", "AE", "AR"


def build_ack(msg: Message, code=ACCEPT, text="", control_id="ACK0001", timestamp="20260101000000"):
    d = msg.delims
    msh = Segment.parse("MSH" + d.field + d.encoding_characters, d)
    msh.set(3, msg.get("MSH", 5))
    msh.set(4, msg.get("MSH", 6))
    msh.set(5, msg.get("MSH", 3))
    msh.set(6, msg.get("MSH", 4))
    msh.set(7, timestamp)
    msh.set(9, "ACK", comp=1)
    msh.set(9, msg.get("MSH", 9, comp=2), comp=2)
    msh.set(10, control_id)
    msh.set(11, msg.get("MSH", 11) or "P")
    msh.set(12, msg.get("MSH", 12) or "2.5")
    msa = Segment.parse("MSA", d)
    msa.set(1, code)
    msa.set(2, msg.control_id)
    if text:
        msa.set(3, text)
    return Message([msh, msa], d)
