"""Heuristic coaching rules for real-time telemetry analysis.

Each rule function takes (packet: dict, state: dict) and returns an alert dict or None.
The state dict is shared across calls so rules can track running averages, streaks, etc.
"""

CORNERS = ["FL", "FR", "RL", "RR"]

# ---------------------------------------------------------------------------
# Tire overheat: alert when any tire temp exceeds 105% of its running average
# for 5+ consecutive packets.
# ---------------------------------------------------------------------------

def check_tire_overheat(packet: dict, state: dict) -> dict | None:
    """Alert when a tire temperature exceeds 105% of its running average for 5+ ticks."""
    if "tire_avg" not in state:
        state["tire_avg"] = {c: {"sum": 0.0, "count": 0} for c in CORNERS}
        state["tire_hot_streak"] = {c: 0 for c in CORNERS}

    for corner in CORNERS:
        key = f"tire_temp_{corner}"
        temp = packet.get(key, 0.0)

        avg_data = state["tire_avg"][corner]
        avg_data["sum"] += temp
        avg_data["count"] += 1
        running_avg = avg_data["sum"] / avg_data["count"]

        threshold = running_avg * 1.05
        if avg_data["count"] > 1 and temp > threshold:
            state["tire_hot_streak"][corner] += 1
        else:
            state["tire_hot_streak"][corner] = 0

        if state["tire_hot_streak"][corner] >= 5:
            label = corner
            return {
                "type": "alert",
                "rule": "tire_overheat",
                "message": f"{label} tire overheating: {temp:.1f} vs avg {running_avg:.1f}",
                "severity": "warn",
            }

    return None


# ---------------------------------------------------------------------------
# Traction loss: alert when TireCombinedSlip > 1.0 for 3+ consecutive packets.
# ---------------------------------------------------------------------------

def check_traction_loss(packet: dict, state: dict) -> dict | None:
    """Alert when any tire's combined slip exceeds 1.0 for 3+ consecutive ticks."""
    if "slip_streak" not in state:
        state["slip_streak"] = {c: 0 for c in CORNERS}

    for corner in CORNERS:
        key = f"tire_combined_slip_{corner}"
        slip = packet.get(key, 0.0)

        if slip > 1.0:
            state["slip_streak"][corner] += 1
        else:
            state["slip_streak"][corner] = 0

        if state["slip_streak"][corner] >= 3:
            label = corner
            return {
                "type": "alert",
                "rule": "traction_loss",
                "message": f"{label} traction loss: combined slip {slip:.2f}",
                "severity": "warn",
            }

    return None


# ---------------------------------------------------------------------------
# Gear selection: alert when an upshift happens below 80% of max RPM.
# An upshift is detected as a large RPM drop between consecutive packets.
# ---------------------------------------------------------------------------

def check_gear_selection(packet: dict, state: dict) -> dict | None:
    """Alert when an upshift is detected below 80% of max RPM."""
    current_rpm = packet.get("current_engine_rpm", 0.0)
    max_rpm = packet.get("engine_max_rpm", 1.0)
    prev_rpm = state.get("prev_rpm")

    state["prev_rpm"] = current_rpm

    if prev_rpm is None:
        return None

    # Detect upshift: RPM drops by more than 30% between ticks
    rpm_drop = prev_rpm - current_rpm
    if rpm_drop > prev_rpm * 0.30 and prev_rpm > 0:
        # Check if the pre-shift RPM was below 80% of max
        if prev_rpm < max_rpm * 0.80:
            return {
                "type": "alert",
                "rule": "gear_selection",
                "message": f"Early upshift at {prev_rpm:.0f}/{max_rpm:.0f} RPM ({prev_rpm / max_rpm * 100:.0f}%)",
                "severity": "info",
            }

    return None


# ---------------------------------------------------------------------------
# Suspension bottoming: alert when NormalizedSuspensionTravel > 0.95.
# ---------------------------------------------------------------------------

def check_suspension_bottoming(packet: dict, state: dict) -> dict | None:
    """Alert when any corner's normalized suspension travel exceeds 0.95."""
    for corner in CORNERS:
        key = f"norm_suspension_travel_{corner}"
        travel = packet.get(key, 0.0)

        if travel > 0.95:
            label = corner
            return {
                "type": "alert",
                "rule": "suspension_bottoming",
                "message": f"{label} suspension bottoming out: travel {travel:.2f}",
                "severity": "warn",
            }

    return None


# All rules in evaluation order
ALL_RULES = [
    check_tire_overheat,
    check_traction_loss,
    check_gear_selection,
    check_suspension_bottoming,
]
