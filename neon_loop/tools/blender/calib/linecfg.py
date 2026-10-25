"""
Feature lines for lines.py.  Each line:
  seed     design2.CURVES name (a graph over x) or a 3D polyline in |y| (monotone along 'axis')
  axis     'x' (default) | 'y' | 'z': the curve is a graph over this coordinate
  range    the fitted range of that coordinate;  dk: B-spline knot spacing (m)
  obs      (photo, side, range or (range, ...), mode, channel, search radius px[, snap options]): trace.py modes:
           dark_above / dark_below (horizontal-ish edges), dark_left / dark_right (vertical-ish), step (either polarity), valley / peak (thin dark / bright line)
  anchors  [(calibrated landmark name or xyz, sigma m)]: the curve passes near these points
  center   True: on the symmetry plane (y = 0);  fixed: coordinates kept at the seed ('y' for the arches: only the profile views fit them, their lip is a rolled edge)
Side -1 = the car's left (the photographed side in all 3/4 and profile shots); p013 / rear views also see side +1.
"""

CFG = {
    # ------------------------------------------------------------------ side
    'U_front': {'seed': 'U', 'range': (-2.40, -1.40), 'dk': 0.2, 'doc': 'U: fender crest, nose corner -> A-pillar root',
                'obs': [('p016', -1, (-2.38, -1.42), 'step', 'lum', 14), ('p018', -1, (-2.38, -1.42), 'step', 'lum', 12),
                        ('p013', -1, (-2.38, -1.42), 'step', 'lum', 12), ('p013', 1, (-2.38, -1.42), 'step', 'lum', 12),
                        ('p003', -1, (-1.90, -1.42), 'step', 'lum', 16)],
                'anchors': [('WA', 0.01)]},
    'U_win': {'seed': 'U', 'range': (-1.37, 1.20), 'dk': 0.2, 'doc': 'side window lower edge (glass / body), A-pillar root -> window tip',
              'obs': [('p018', -1, (-0.40, 1.19), 'dark_above', 'lum', 12), ('p001', -1, (0.35, 1.19), 'dark_above', 'lum', 12),
                      ('p017', -1, (-1.30, 1.19), 'dark_above', 'lum', 12), ('p011', -1, (-1.30, 1.19), 'dark_above', 'lum', 12),
                      ('p016', -1, (-1.30, 1.10), 'dark_above', 'lum', 12),
                      ('p013', -1, (-1.30, 1.15), 'step', 'lum', 12), ('p013', 1, (-1.30, 1.15), 'step', 'lum', 12)]},
    'wl': {'seed': 'wl', 'range': (-1.37, 1.15), 'dk': 0.2, 'doc': 'side window upper edge (glass / roof-rail band)',
           'obs': [('p018', -1, (-1.30, 1.14), 'dark_below', 'lum', 14), ('p001', -1, (0.35, 1.14), 'dark_below', 'lum', 14),
                   ('p017', -1, (-1.30, 1.14), 'dark_below', 'lum', 14), ('p011', -1, (-1.30, 1.14), 'dark_below', 'lum', 14),
                   ('p016', -1, (-1.30, 1.10), 'dark_below', 'lum', 14)]},
    'L_front': {'seed': 'L', 'range': (-2.46, -1.86), 'dk': 0.15, 'doc': 'L ahead of the front wheel (nose corner -> arch)',
                'obs': [('p001', -1, (-2.35, -1.90), 'dark_below', 'lum', 14), ('p018', -1, (-2.35, -1.90), 'dark_below', 'lum', 14),
                        ('p016', -1, (-2.40, -1.90), 'step', 'lum', 14), ('p013', -1, (-2.40, -1.90), 'step', 'lum', 14), ('p013', 1, (-2.40, -1.90), 'step', 'lum', 14)]},
    'L_side': {'seed': 'L', 'range': (-1.22, 2.41), 'dk': 0.3, 'doc': 'L behind the front wheel: shoulder crease to the tail corner',
               'obs': [('p018', -1, (-1.05, 2.35), 'dark_below', 'lum', 14), ('p001', -1, (0.35, 2.35), 'dark_below', 'lum', 14),
                       ('p017', -1, (-1.05, 2.35), 'step', 'lum', 14), ('p011', -1, (-1.05, 2.35), 'step', 'lum', 14),
                       ('p016', -1, (-1.05, 1.60), 'step', 'lum', 14),
                       ('p013', -1, (-1.05, 2.35), 'step', 'lum', 14), ('p013', 1, (-1.05, 2.35), 'step', 'lum', 14)],
               'anchors': [('TP', 0.015)]},
    'l3': {'seed': 'l3', 'range': (-1.15, 1.25), 'dk': 0.3, 'doc': 'upper edge of the black lower zone (paint / black)',
           'obs': [('p018', -1, (-1.05, 1.20), 'dark_below', 'lum', 45), ('p001', -1, (0.35, 1.20), 'dark_below', 'lum', 45),
                   ('p017', -1, (-1.05, 1.20), 'dark_below', 'lum', 45), ('p011', -1, (-1.05, 1.20), 'dark_below', 'lum', 45),
                   ('p016', -1, (-1.05, 1.20), 'dark_below', 'lum', 45)]},
    'DS_front': {'seed': [(-0.799, 0.997, 0.286), (-0.85, 1.04, 0.52), (-0.896, 1.064, 0.739), (-0.915, 1.00, 0.80), (-0.93, 0.93, 0.865)], 'axis': 'z',
                 'range': (0.29, 0.86), 'dk': 0.15, 'doc': 'front door seam (blade / door / shoulder junction DFJ), sill -> window line',
                 'obs': [('p018', -1, (0.30, 0.85), 'valley', 'lum', 10), ('p017', -1, (0.30, 0.85), 'valley', 'lum', 10), ('p011', -1, (0.30, 0.85), 'valley', 'lum', 10),
                         ('p016', -1, (0.30, 0.85), 'valley', 'lum', 10), ('p003', -1, (0.30, 0.85), 'valley', 'lum', 14)],
                 'anchors': [('DS1b', 0.01), ('DFJ', 0.01)]},
    'DS_rear': {'seed': [(0.264, 1.016, 0.336), (0.29, 1.05, 0.55), (0.34, 1.06, 0.75), (0.40, 1.06, 0.88), (0.47, 0.95, 0.94), (0.52, 0.86, 0.995)], 'axis': 'z',
                'range': (0.34, 0.86), 'dk': 0.15, 'doc': 'rear door seam, black zone -> shoulder L',
                'obs': [('p018', -1, (0.35, 0.85), 'valley', 'lum', 20), ('p017', -1, (0.35, 0.85), 'valley', 'lum', 20), ('p011', -1, (0.35, 0.85), 'valley', 'lum', 20),
                        ('p016', -1, (0.35, 0.85), 'valley', 'lum', 20)],
                'anchors': [('DS2b', 0.01)]},
    # ------------------------------------------------------------------ rear-corner facet (SPEC L12; added in phase 3 to place the rear end: CALIB.md phase 3)
    'seam_F': {'seed': [(2.149, 0.988, 0.733), (2.06, 1.022, 0.857), (1.972, 1.056, 0.981)], 'axis': 'z', 'range': (0.745, 0.97), 'dk': 0.1,
               'doc': 'front edge of the rear-corner facet (the wing endplate seam), l3 -> L',
               'obs': [('p018', -1, (0.75, 0.97), 'valley', 'lum', 14), ('p001', -1, (0.75, 0.97), 'valley', 'lum', 14), ('p017', -1, (0.75, 0.97), 'valley', 'lum', 14),
                       ('p011', -1, (0.75, 0.97), 'valley', 'lum', 14)]},
    'facet_R': {'seed': [(2.337, 0.943, 0.807), (2.355, 0.945, 0.90), (2.368, 0.946, 0.995)], 'axis': 'z', 'range': (0.815, 0.985), 'dk': 0.1,
                'doc': 'rear edge of the rear-corner facet (facet | black tail panel side), PBc -> TP',
                'obs': [('p018', -1, (0.82, 0.98), 'step', 'lum', 16), ('p001', -1, (0.82, 0.98), 'step', 'lum', 16), ('p017', -1, (0.82, 0.98), 'step', 'lum', 16),
                        ('p011', -1, (0.82, 0.98), 'step', 'lum', 16), ('p012', -1, (0.82, 0.98), 'step', 'lum', 16), ('p019', -1, (0.82, 0.98), 'step', 'lum', 16)]},
    # ------------------------------------------------------------------ roof / glass
    'rail': {'seed': 'rail', 'range': (-0.40, 2.41), 'dk': 0.25, 'doc': 'roof rail: upper edge of the body-colour band (glass dome above), then the rear crest R-1',
             'obs': [('p018', -1, (-0.35, 2.30), 'dark_above', 'lum', 12), ('p001', -1, (0.40, 2.30), 'dark_above', 'lum', 12),
                     ('p017', -1, (-0.35, 2.35), 'step', 'lum', 12), ('p011', -1, (-0.35, 2.35), 'step', 'lum', 12), ('p016', -1, (-0.35, 1.20), 'step', 'lum', 12),
                     ('p013', -1, (-0.35, 2.35), 'step', 'lum', 12), ('p013', 1, (-0.35, 2.35), 'step', 'lum', 12),
                     ('high', -1, (0.90, 2.35), 'step', 'lum', 12), ('high', 1, (0.90, 2.35), 'step', 'lum', 12),
                     ('p002', -1, (0.90, 2.35), 'step', 'lum', 12), ('p002', 1, (0.90, 2.35), 'step', 'lum', 12)]},
    'pillar': {'seed': 'pillar_in', 'range': (-1.44, -0.40), 'dk': 0.2, 'doc': 'A-pillar inner edge (pillar / windscreen glass)',
               'obs': [('p016', -1, (-1.40, -0.45), 'step', 'lum', 12), ('p013', -1, (-1.40, -0.45), 'step', 'lum', 12), ('p013', 1, (-1.40, -0.45), 'step', 'lum', 12),
                       ('p018', -1, (-1.40, -0.45), 'step', 'lum', 10)]},
    'rglass': {'seed': 'gedge', 'range': (1.45, 2.10), 'dk': 0.2, 'doc': 'rear window side edge (glass / triangle band R-3) -> P3',
               'obs': [('p013', -1, (1.47, 2.08), 'step', 'lum', 12), ('p013', 1, (1.47, 2.08), 'step', 'lum', 12),
                       ('high', -1, (1.47, 2.08), 'step', 'lum', 12), ('high', 1, (1.47, 2.08), 'step', 'lum', 12),
                       ('p002', -1, (1.47, 2.08), 'step', 'lum', 12), ('p002', 1, (1.47, 2.08), 'step', 'lum', 12),
                       ('r81', -1, (1.50, 2.08), 'step', 'lum', 8), ('r81', 1, (1.50, 2.08), 'step', 'lum', 8)],
               'anchors': [('P3', 0.01)]},
    # ------------------------------------------------------------------ front
    'L5': {'seed': 'L5', 'range': (-2.46, -1.625), 'dk': 0.2, 'doc': 'L5 hood crease: lamp-bar end -> windscreen lower corner',
           'obs': [('p016', -1, (-2.40, -1.66), 'step', 'lum', 12), ('p016', 1, (-2.40, -1.66), 'step', 'lum', 12),
                   ('p013', -1, (-2.40, -1.66), 'step', 'lum', 12), ('p013', 1, (-2.40, -1.66), 'step', 'lum', 12),
                   ('p014', -1, (-2.40, -1.66), 'step', 'lum', 12), ('p014', 1, (-2.40, -1.66), 'step', 'lum', 12)]},

    # ------------------------------------------------------------------ wheel arches (upper part, graph over x)
    'arch_F': {'fixed': 'y', 'seed': [(-1.8586, 1.03, 0.5633), (-1.8194, 1.03, 0.63), (-1.7684, 1.03, 0.6882), (-1.7073, 1.03, 0.7358), (-1.6384, 1.03, 0.771), (-1.5641, 1.03, 0.7927), (-1.487, 1.03, 0.8), (-1.4099, 1.03, 0.7927), (-1.3356, 1.03, 0.771), (-1.2667, 1.03, 0.7358), (-1.2056, 1.03, 0.6882), (-1.1546, 1.03, 0.63), (-1.1154, 1.03, 0.5633)], 'range': (-1.84, -1.13), 'dk': 0.12, 'doc': 'front wheel arch lip in side elevation (|y| kept at 1.03)',
               'obs': [('p018', -1, (-1.83, -1.14), 'step', 'lum', 14), ('p001', -1, (-1.83, -1.14), 'step', 'lum', 14)]},
    'arch_R': {'fixed': 'y', 'seed': [(1.2384, 1.03, 0.5633), (1.2776, 1.03, 0.63), (1.3286, 1.03, 0.6882), (1.3897, 1.03, 0.7358), (1.4586, 1.03, 0.771), (1.5329, 1.03, 0.7927), (1.61, 1.03, 0.8), (1.6871, 1.03, 0.7927), (1.7614, 1.03, 0.771), (1.8303, 1.03, 0.7358), (1.8914, 1.03, 0.6882), (1.9424, 1.03, 0.63), (1.9816, 1.03, 0.5633)], 'range': (1.25, 1.96), 'dk': 0.12, 'doc': 'rear wheel arch lip in side elevation (|y| kept at 1.03)',
               'obs': [('p018', -1, (1.26, 1.95), 'step', 'lum', 14), ('p001', -1, (1.26, 1.95), 'step', 'lum', 14)]},
    # ------------------------------------------------------------------ front face
    'lamp_bar': {'seed': [(-2.57, 0.0, 0.541), (-2.5678, 0.0957, 0.541), (-2.561, 0.1914, 0.541), (-2.5498, 0.2871, 0.541), (-2.5341, 0.3829, 0.541), (-2.5139, 0.4786, 0.541), (-2.4892, 0.5743, 0.541), (-2.46, 0.67, 0.541)], 'axis': 'y', 'range': (0.0, 0.70), 'dk': 0.12, 'doc': 'front light bar L4 (thin bright strip), centre -> end FB',
                 'obs': [('p014', -1, (0.0, 0.66), 'peak', 'lum', 14, {'w': 6.0}), ('p014', 1, (0.0, 0.66), 'peak', 'lum', 14, {'w': 6.0}),
                         ('p016', -1, (0.0, 0.66), 'peak', 'lum', 22, {'w': 4.0}), ('p016', 1, (0.0, 0.66), 'peak', 'lum', 22, {'w': 4.0})],
                 'anchors': [('FB', 0.01)]},
    # ------------------------------------------------------------------ tail
    'tail_bar': {'seed': [(2.40, 0.0, 0.941), (2.405, 0.5, 0.941), (2.409, 0.941, 0.941)], 'axis': 'y', 'range': (0.0, 0.94), 'dk': 0.15,
                 'doc': 'red tail light bar (centre -> end TB)',
                 'obs': [('r81', -1, (0.0, 0.93), 'peak', 'red', 8), ('r81', 1, (0.0, 0.93), 'peak', 'red', 8), ('high', -1, (0.0, 0.93), 'peak', 'red', 10), ('high', 1, (0.0, 0.93), 'peak', 'red', 10),
                         ('p002', -1, (0.0, 0.93), 'peak', 'red', 10), ('p002', 1, (0.0, 0.93), 'peak', 'red', 10), ('p012', -1, (0.0, 0.93), 'peak', 'red', 10), ('p012', 1, (0.0, 0.93), 'peak', 'red', 10),
                         ('p017', 1, (0.0, 0.93), 'peak', 'red', 10), ('p017', -1, (0.0, 0.93), 'peak', 'red', 10), ('p011', -1, (0.0, 0.93), 'peak', 'red', 10), ('p011', 1, (0.0, 0.93), 'peak', 'red', 10)],
                 'anchors': [('TB', 0.01)]},
    'tail_top': {'seed': [(2.43, 0.0, 0.99), (2.43, 0.5, 0.99), (2.43, 0.944, 0.99)], 'axis': 'y', 'range': (0.0, 0.944), 'dk': 0.15,
                 'doc': 'top edge of the black tail panel (under the visor), centre -> corner TP',
                 'obs': [('r81', -1, (0.0, 0.92), 'dark_below', 'lum', 8), ('r81', 1, (0.0, 0.92), 'dark_below', 'lum', 8), ('p012', -1, (0.0, 0.92), 'dark_below', 'lum', 10), ('p012', 1, (0.0, 0.92), 'dark_below', 'lum', 10),
                         ('p019', -1, (0.0, 0.92), 'dark_below', 'lum', 10), ('p019', 1, (0.0, 0.92), 'dark_below', 'lum', 10), ('p017', -1, (0.0, 0.92), 'dark_below', 'lum', 10), ('p017', 1, (0.0, 0.92), 'dark_below', 'lum', 10),
                         ('p011', -1, (0.0, 0.92), 'dark_below', 'lum', 10), ('p011', 1, (0.0, 0.92), 'dark_below', 'lum', 10)],
                 'anchors': [('TP', 0.01)]},
    'tail_bot': {'seed': [(2.415, 0.0, 0.85), (2.415, 0.5, 0.85), (2.415, 0.953, 0.85)], 'axis': 'y', 'range': (0.0, 0.953), 'dk': 0.15,
                 'doc': 'bottom edge of the black tail panel (bright surface below), centre -> corner PBc',
                 'obs': [('r81', -1, (0.0, 0.93), 'dark_above', 'lum', 8), ('r81', 1, (0.0, 0.93), 'dark_above', 'lum', 8), ('high', -1, (0.0, 0.93), 'dark_above', 'lum', 10), ('high', 1, (0.0, 0.93), 'dark_above', 'lum', 10),
                         ('p002', -1, (0.0, 0.93), 'dark_above', 'lum', 10), ('p002', 1, (0.0, 0.93), 'dark_above', 'lum', 10), ('p012', -1, (0.0, 0.93), 'dark_above', 'lum', 10), ('p012', 1, (0.0, 0.93), 'dark_above', 'lum', 10),
                         ('p017', 1, (0.0, 0.93), 'dark_above', 'lum', 10), ('p017', -1, (0.0, 0.93), 'dark_above', 'lum', 10), ('p011', -1, (0.0, 0.93), 'dark_above', 'lum', 10), ('p011', 1, (0.0, 0.93), 'dark_above', 'lum', 10)],
                 'anchors': [('PBc', 0.01)]},
}
