"""B-only exact parsing/projection reuse; no search or A checker conclusions.

Drop-in audit/projections/audit_projection/make_certificate functions preserve
PR133 dictionaries exactly. A and B still derive their own certificate bounds.
All caches are scoped to one call and contain parsed Fraction inputs, not trusted
search lower/upper values. Protocol projections retain every leaf and its area
multiplicity, unlike the deliberately deduplicated B rectangle representation.
"""
from collections import Counter
from fractions import Fraction as F
from itertools import product

from certificate import RationalEvaluator, retained, root
from a_bridge import MODE, root30, protocol_recovery


class Parser:
    """Memoize exact scalar parsing and boxes within one record operation."""
    def __init__(self):
        self.scalars = {}
        self.boxes = {}

    def scalar(self, value):
        key = (type(value), value)
        if key not in self.scalars:
            self.scalars[key] = F(value)
        return self.scalars[key]

    def box(self, value):
        key = tuple(tuple(v) for v in value)
        if key not in self.boxes:
            self.boxes[key] = tuple(tuple(self.scalar(x) for x in v) for v in value)
        return self.boxes[key]


def audit(m, method, s, r):
    """Same full-tree checks and independent rational bounds as PR133 audit."""
    assert method in ('J5', 'P4', 'N4')
    dim = 5 if method == 'J5' else 4
    assert r['dimension'] == dim
    nodes = {n['path']: n for n in r['nodes']}
    assert len(nodes) == len(r['nodes'])
    parse = Parser()
    domain = parse.box(m['domain'] + ([m['bias_domain']] if method == 'J5' else []))
    assert parse.box(nodes['']['box']) == domain
    q = F(s['q'])
    stack, seen, certs = [''], set(), 0
    evaluate_bound = RationalEvaluator(m, method)
    while stack:
        path = stack.pop()
        assert path not in seen
        seen.add(path)
        n = nodes[path]
        b = parse.box(n['box'])
        assert len(b) == dim and all(a <= z for a, z in b)
        if n['status'] == 'SPLIT':
            j, mid = n['axis'], parse.scalar(n['mid'])
            assert 0 <= j < dim and b[j][0] < mid < b[j][1]
            for side in (0, 1):
                child = list(b)
                child[j] = (b[j][0], mid) if side == 0 else (mid, b[j][1])
                cp = path + str(side)
                assert parse.box(nodes[cp]['box']) == tuple(child)
                stack.append(cp)
        elif n['status'] in ('OUTSIDE', 'INSIDE'):
            lo, hi = evaluate_bound(b)
            assert lo > q if n['status'] == 'OUTSIDE' else hi <= q
            certs += 1
        else:
            assert n['status'] in ('PENDING', 'UNDECIDED', 'NUMERICAL_UNDECIDED')
    assert seen == set(nodes)
    assert sorted(r['queue']) == sorted(n['path'] for n in nodes.values() if n['status'] == 'PENDING')
    assert r['counts'] == dict(Counter(n['status'] for n in nodes.values()))
    assert r['processed'] == sum(n['status'] != 'PENDING' for n in nodes.values())
    kept_count = sum(n['status'] not in ('OUTSIDE', 'SPLIT') for n in r['nodes'])
    assert r['empty_proved'] == (kept_count == 0)
    return dict(status='PASS', nodes=len(nodes), certified_leaves=certs, retained=kept_count)


def encode(box):
    return [[str(a), str(z)] for a, z in box]


def _projections(m, r, parse):
    kept = [(n['status'], parse.box(n['box'])) for n in retained(r)]
    domain = parse.box(m['domain'])
    out = {}
    for car, offset in [('p', 0), ('s', 2)]:
        rects = sorted(set(b[offset:offset + 2] for _, b in kept))
        inner = sorted(set(b[offset:offset + 2] for status, b in kept if status == 'INSIDE'))
        unresolved = sorted(set(b[offset:offset + 2] for status, b in kept if status != 'INSIDE'))
        if not rects:
            out[car] = dict(rectangles=[], inside_rectangles=[], unresolved_rectangles=[], hull=None,
                            center=None, radius_upper_m=None, area_upper_m2='0', feasible_area_lower_m2='0',
                            span_m=None, boundary_contact=False, branch_evidence={})
            continue
        hull = tuple((min(b[j][0] for b in rects), max(b[j][1] for b in rects)) for j in range(2))
        center = tuple((a + b) / 2 for a, b in hull)
        area = lambda b: (b[0][1] - b[0][0]) * (b[1][1] - b[1][0])
        area_upper = min(sum(map(area, rects)), area(hull))
        rad2 = max(sum(max((v - center[j]) ** 2 for v in b[j]) for j in range(2)) for b in rects)
        boundary = any(any(b[j][k] == domain[offset + j][k] for j in range(2) for k in (0, 1)) for b in rects)
        evidence = {}
        for label, test in [('negative_y', lambda b: b[1][0] < 0), ('positive_y', lambda b: b[1][1] > 0)]:
            evidence[label] = dict(candidate_rectangles=sum(test(b) for b in rects),
                                   certified_inside_rectangles=sum(test(b) for b in inner))
        out[car] = dict(rectangles=[encode(b) for b in rects], inside_rectangles=[encode(b) for b in inner],
                        unresolved_rectangles=[encode(b) for b in unresolved], hull=encode(hull),
                        center=list(map(str, center)), radius_upper_m=str(root((rad2, rad2))[1]),
                        area_upper_m2=str(area_upper), feasible_area_lower_m2=str(max(map(area, inner), default=F(0))),
                        span_m=[str(b - a) for a, b in hull], boundary_contact=boundary, branch_evidence=evidence)
    return out


def projections(m, r):
    return _projections(m, r, Parser())


def audit_projection(m, r, proj):
    """Still reconstructs every field and checks all four rectangle corners."""
    parse = Parser()
    assert proj == _projections(m, r, parse)
    for car in ('p', 's'):
        z = proj[car]
        if not z['rectangles']:
            continue
        c = [parse.scalar(x) for x in z['center']]
        rr = parse.scalar(z['radius_upper_m']) ** 2
        for b in map(parse.box, z['rectangles']):
            assert all(sum((x - c[i]) ** 2 for i, x in enumerate(v)) <= rr for v in product(*b))
    return dict(status='PASS', cars=2)


def protocol_projections(nodes, parse=None):
    """A-format projection: preserve leaf list and duplicate-area multiplicity."""
    parse = Parser() if parse is None else parse
    kept = [n for n in nodes if n['kind'] in ('INSIDE', 'UNDECIDED', 'PENDING')]
    boxes = [parse.box(n['box']) for n in kept]
    out = {}
    for car, offset in [('p', 0), ('s', 2)]:
        rects = [dict(leaf=n['id'], box=n['box'][offset:offset + 2]) for n in kept]
        if not rects:
            out[car] = dict(rectangles=[], center=None, radius=None, radius_squared=None, area_upper='0')
            continue
        # Exact rational operations permit aggregation of repeated rectangle terms.
        multiplicity = Counter(b[offset:offset + 2] for b in boxes)
        bs = list(multiplicity)
        lo = [min(b[j][0] for b in bs) for j in range(2)]
        hi = [max(b[j][1] for b in bs) for j in range(2)]
        center = [(a + z) / 2 for a, z in zip(lo, hi)]
        rad2 = max(sum(max((v - center[j]) ** 2 for v in b[j]) for j in range(2)) for b in bs)
        area = min((hi[0] - lo[0]) * (hi[1] - lo[1]),
                   sum((b[0][1] - b[0][0]) * (b[1][1] - b[1][0]) * count for b, count in multiplicity.items()))
        out[car] = dict(rectangles=rects, center=list(map(str, center)), radius=str(root30(rad2)[1]),
                        radius_squared=str(rad2), area_upper=str(area))
    return out


def make_certificate(case, method, settings, result, projection, cost=None):
    """Same A certificate bytes under canonical JSON; no checking performed here."""
    x = case['a_input']
    nodes = []
    for n in result['nodes']:
        if n['status'] == 'NUMERICAL_UNDECIDED':
            raise RuntimeError('A_SCHEMA_NUMERICAL_STATE_UNSUPPORTED')
        z = dict(id=n['path'], box=n['box'], kind=n['status'])
        if n['status'] == 'SPLIT':
            z.update(axis=n['axis'], cut=n['mid'], children=[n['path'] + '0', n['path'] + '1'])
        nodes.append(z)
    mode = MODE[method]
    count = {k: sum(n['kind'] == k for n in nodes) for k in ('SPLIT', 'OUTSIDE', 'INSIDE', 'UNDECIDED', 'PENDING')}
    keep = [n for n in nodes if n['kind'] not in ('SPLIT', 'OUTSIDE')]
    parse = Parser()
    domain = parse.box(x['domains'])
    contact = any(any(a == c or b == d for (a, b), (c, d) in zip(parse.box(n['box']), domain)) for n in keep)
    ap = protocol_projections(nodes, parse)
    rec = []
    if method == 'P4' and keep:
        pos = ap['p']['center'] + ap['s']['center']
        rec = [dict(point=pos, result=protocol_recovery(x, pos))]
    threshold = dict(x['threshold_certificate'])
    if method == 'N4':
        threshold.update(id='DUAL-A-V1-CHI2-8-CHERNOFF', dimension=8, tau='24')
    if cost is None:
        cost = dict(processed_nodes=result['processed'], search_seconds=str(result['search_seconds']),
                    certificate_write_seconds='0', peak_rss_bytes='0', distance_evaluations=result.get('distance_evaluations', 0))
    return dict(schema_version='DUAL-A-V1', input_hash=x['input_hash'], source_commit=x['source_commit'], mode=mode,
                measurement_ids=x['measurement_ids'][:8 if method == 'N4' else 9], threshold_certificate=threshold,
                root='', nodes=nodes, queue=result['queue'], projections=ap, counts=count,
                status='EMPTY_IN_DECLARED_DOMAIN' if not keep else 'BUDGET_OUTER' if result['queue'] else 'OUTER_CERTIFIED',
                domain_contact=contact, internal_semantics={'J5': 'forall_state_exists_observation',
                'P4': 'forall_position_exists_bias_and_observation', 'N4': 'forall_position_exists_observation'}[method],
                bias_recovery=rec, cost=cost)
