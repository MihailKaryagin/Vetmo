"""Valve portraits; internal names verified against OpenDota's hero catalog.

Source: https://github.com/odota/dotaconstants/blob/master/build/heroes.json
Unknown names remain readable text instead of producing broken image URLs.
"""

HERO_NAMES = {
    name.casefold(): slug for name, slug in (
        ('Juggernaut', 'juggernaut'), ('Luna', 'luna'), ('Lifestealer', 'life_stealer'),
        ('Puck', 'puck'), ('Ember Spirit', 'ember_spirit'), ('Storm Spirit', 'storm_spirit'),
        ('Mars', 'mars'), ('Underlord', 'abyssal_underlord'), ('Centaur Warrunner', 'centaur'),
        ('Rubick', 'rubick'), ('Tusk', 'tusk'), ('Hoodwink', 'hoodwink'),
        ('Oracle', 'oracle'), ('Jakiro', 'jakiro'), ('Disruptor', 'disruptor'),
        ('Morphling', 'morphling'), ('Terrorblade', 'terrorblade'), ('Sven', 'sven'),
        ('Dark Willow', 'dark_willow'), ('Lion', 'lion'), ('Mirana', 'mirana'),
        ('Queen of Pain', 'queenofpain'), ('Leshrac', 'leshrac'), ('Void Spirit', 'void_spirit'),
        ('Invoker', 'invoker'), ('Pudge', 'pudge'), ('Anti-Mage', 'antimage'),
        ('Crystal Maiden', 'crystal_maiden'), ('Shadow Fiend', 'nevermore'),
        ('Drow Ranger', 'drow_ranger'), ('Axe', 'axe'), ('Earthshaker', 'earthshaker'),
        ('Windranger', 'windrunner'), ('Wraith King', 'skeleton_king'),
        ('Enchantress', 'enchantress'), ('Echantress', 'enchantress'),
        ('Clockwerk', 'rattletrap'), ('Nyx', 'nyx_assassin'), ('Nyx Assassin', 'nyx_assassin'),
        ('Riki', 'riki'), ('Ogre Magi', 'ogre_magi'),
    )
}


def hero_portraits(value):
    heroes = []
    for name in (part.strip() for part in value.split(',')):
        if not name:
            continue
        slug = HERO_NAMES.get(name.casefold())
        heroes.append({'name': name, 'image': f'https://cdn.steamstatic.com/apps/dota2/images/dota_react/heroes/{slug}.png' if slug else ''})
        if len(heroes) == 3:
            break
    return heroes
