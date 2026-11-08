import json
from pathlib import Path

roman_value = '''"""Integer value of a Roman numeral."""

def roman_value(text):
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    previous = 0
    for ch in reversed(text.upper()):
        current = values.get(ch, 0)
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return total
'''

tip_split = '''"""Split a tip so each diner gets whole cents."""

def tip_shares(bill_cents, percent, diners):
    if diners < 1 or bill_cents < 0 or percent < 0:
        return []
    total = (bill_cents * percent) // 100
    base, extra = divmod(total, diners)
    shares = []
    seat = 0
    while seat < diners:
        bonus = 1 if seat < extra else 0
        shares.append(base + bonus)
        seat += 1
    return shares
'''

dim_weight = '''"""Billable pounds from the greater of scale and dim weight."""

def dim_pounds(length_in, width_in, height_in):
    cubic = length_in * width_in * height_in
    if cubic < 1:
        return 0
    return (cubic + 138) // 139

def billable_pounds(scale, length_in, width_in, height_in):
    if scale < 0 or length_in < 0 or width_in < 0 or height_in < 0:
        return 0
    guessed = dim_pounds(length_in, width_in, height_in)
    if guessed > scale:
        return guessed
    return scale
'''

compass_name = '''"""Snap a degree heading to an eight-point compass name."""

def compass_name(degrees):
    names = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    turned = degrees % 360
    index = ((turned + 22) // 45) % 8
    return names[index]
'''

scarf_rows = '''"""Rows to knit so a scarf reaches a target length."""

def rows_for_length(target_in, rows_per_four):
    if target_in <= 0 or rows_per_four <= 0:
        return 0
    needed = target_in * rows_per_four
    return (needed + 3) // 4
'''

batter_scale = '''"""Scale a batter amount when the pan area changes."""

def pan_area(length, width):
    if length < 0 or width < 0:
        return 0
    return length * width

def scale_batter(amount, old_pan, new_pan):
    if amount < 0:
        return 0
    old_area = pan_area(old_pan[0], old_pan[1])
    new_area = pan_area(new_pan[0], new_pan[1])
    if old_area == 0:
        return 0
    return amount * new_area // old_area
'''

letter_post = '''"""Postage in cents for a letter from weight in ounces."""

FIRST_OUNCE = 73
EXTRA_OUNCE = 28

def ounce_rate(ounces):
    if ounces <= 1:
        return FIRST_OUNCE
    return FIRST_OUNCE + (ounces - 1) * EXTRA_OUNCE

def letter_postage(ounces):
    if ounces < 1:
        return 0
    return ounce_rate(ounces)

if __name__ == "__main__":
    letter_postage(3)
'''

pantry_jar = '''"""A labeled jar on a pantry shelf."""

class PantryJar:
    def __init__(self, item, ounces):
        self.item = item
        self.ounces = ounces

    def tag(self):
        return f"{self.item} ({self.ounces} oz)"

    def fits(self, space_oz):
        return self.ounces <= space_oz
'''

files = [
    ("roman_value.py", roman_value),
    ("tip_split.py", tip_split),
    ("dim_weight.py", dim_weight),
    ("compass_name.py", compass_name),
    ("scarf_rows.py", scarf_rows),
    ("batter_scale.py", batter_scale),
    ("letter_post.py", letter_post),
    ("pantry_jar.py", pantry_jar),
]
out = Path(__file__).with_name("round3-proposals.json")
out.write_text(json.dumps([{"name": n, "source": s} for n, s in files], indent=2), encoding="utf-8")
print(out)
