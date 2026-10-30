"""Small reviewed exceptions, bound to both the key and the exact EN source.

Never infer that arbitrary English is a brand or cognate. A source change
invalidates the exception and returns the entry to normal translation/review.
"""
REVIEWED_UNCHANGED = {
    ('IGUI_FancyHotelKey', 'Hotel'),
    ('IGUI_HotelRichKey', 'Hotel'),
    ('IGUI_hospitalroomKey', 'Hospital'),
    ('IGUI_GigamartKey', 'GigaMart'),
    ('IGUI_GigaMart', 'GigaMart'),
    ('IGUI_Greenes', "Greene's"),
    ('IGUI_GreenesKey', "Greene's"),
    ('Print_Text_GreenesJobAdEkron_title', "Greene's"),
}


def reviewed_unchanged(key, en):
    return (key, en) in REVIEWED_UNCHANGED
