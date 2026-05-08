# Child safety gate — suppress dangerous tools when interacting with minors.
#
# The mode signal represents "minor interaction probability":
#   0.0 = verified adult
#   0.5 = age unknown
#   1.0 = confirmed minor
#
# Tools that could harm a minor are structurally removed from the
# LLM's catalog. The model cannot be prompt-injected into using a
# tool that doesn't exist in its world.

from gatekeeper import Gate, Tool

# --- Define messaging tools with safety classifications ---

gate = Gate()
gate.add_tools([
    # Always available — safe for any age
    Tool("send_text_message",       execution_class="read_only",       description="Send a text message"),
    Tool("share_educational_link",  execution_class="advisory",        description="Share an educational resource"),
    Tool("report_concern",          execution_class="advisory",        description="Flag content for human review"),

    # Suppressed when minor is likely (mode > 0.65)
    Tool("share_image",             execution_class="external_action", description="Share an image"),
    Tool("share_location",          execution_class="external_action", description="Share current location"),
    Tool("request_phone_number",    execution_class="state_mutation",  description="Ask for phone number"),

    # Suppressed when age is unknown or minor (mode > 0.35)
    Tool("request_home_address",    execution_class="high_impact",     description="Ask for home address"),
    Tool("schedule_private_meeting",execution_class="high_impact",     description="Schedule an in-person meeting"),
    Tool("share_adult_content",     execution_class="high_impact",     description="Share age-restricted content"),
])

# --- Verified adult: all tools available ---
adult = gate.filter(mode=0.0)
print(f"Adult ({len(adult.visible)} tools): {adult.visible_names}")
# All 9 tools visible

# --- Age unknown: high_impact suppressed ---
unknown = gate.filter(mode=0.5)
print(f"Age unknown ({len(unknown.visible)} tools): {unknown.visible_names}")
print(f"  Suppressed: {unknown.suppressed_names}")
# request_home_address, schedule_private_meeting, share_adult_content gone

# --- Confirmed minor: only safe tools remain ---
minor = gate.filter(mode=0.9)
print(f"Minor ({len(minor.visible)} tools): {minor.visible_names}")
print(f"  Suppressed: {minor.suppressed_names}")
# Only: send_text_message, share_educational_link, report_concern

# --- The key point ---
print()
print("An LLM talking to a minor cannot propose 'schedule_private_meeting'")
print("because that tool does not exist in its catalog. Not refused — absent.")
