"""Contract-only deterministic auditing for H1, H3 and H4. Never reads labels."""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import csv
import json
import re
from pathlib import Path

from vocabulary import tokens

UNITS = {'per hour': 'per_hour', 'per visit': 'per_visit',
         'per procedure': 'per_procedure', 'per test': 'per_test',
         'per day of service': 'per_day', 'per night of occupancy': 'per_night',
         'per item supplied': 'per_item', 'per unit dispensed': 'per_unit_dispensed'}


def integer(value):
    d = Decimal(str(value))
    if not d.is_finite() or d != d.to_integral_value():
        raise ValueError(f'Expected finite integer, got {value!r}')
    return int(d)


def adjusted(rate, percent):
    return int((Decimal(rate) * Decimal(100 + percent) / 100).quantize(
        Decimal('1'), rounding=ROUND_HALF_UP))


def parse_date(value):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(value)):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@dataclass
class Contract:
    hospital: int
    number: str
    start: date
    end: date
    services: dict
    premiums: dict = field(default_factory=dict)
    caps: dict = field(default_factory=dict)
    weekends: dict = field(default_factory=dict)
    discounts: dict = field(default_factory=dict)
    bundles: dict = field(default_factory=dict)
    exclusions: dict = field(default_factory=dict)
    amended_rates: dict = field(default_factory=dict)
    introduced_on: dict = field(default_factory=dict)
    amendment_date: date = None


def parse_contract(root, hospital):
    filename = {1: 'provider_services_agreement.txt', 3: 'base_agreement.txt',
                4: 'conditional_reimbursement_agreement.txt'}[hospital]
    text = (Path(root) / 'contracts' / f'hospital_{hospital}' / filename).read_text(encoding='utf-8-sig')
    sections = {}
    headings = list(re.finditer(r'(?m)^(\d+)\. ([A-Z][A-Z -]+)\s*$', text))
    for i, match in enumerate(headings):
        sections[int(match[1])] = text[match.end():headings[i+1].start() if i+1 < len(headings) else len(text)]
    def header(key):
        return re.search(rf'(?m)^{key}: (.+)$', text)[1].strip()
    c = Contract(hospital, header('Contract number'),
                 datetime.strptime(header('Effective from'), '%d %B %Y').date(),
                 datetime.strptime(header('Effective to'), '%d %B %Y').date(), {})
    rate_text = sections[4 if hospital == 1 else 3]
    if hospital == 3:
        rate_text = (Path(root)/'contracts/hospital_3/appendix_b_rate_schedule.txt').read_text(encoding='utf-8-sig')
        if f'Contract number: {c.number}' not in rate_text:
            raise ValueError('H3 appendix has a different contract number')
    for row in rate_text.splitlines():
        m = re.match(r'^(.+?)\s{2,}(per .+?)\s{2,}GBP ([\d,.]+)(?:\s+.*)?$', row)
        if m:
            name, unit, amount = m.groups()
            c.services[name.strip()] = {'unit': UNITS.get(unit.strip()),
                'unit_text': unit.strip(), 'rate': integer(Decimal(amount.replace(',', '')) * 100)}
    for row in sections[4 if hospital == 3 else 5].splitlines():
        m = re.match(r'^(.+?)\s{2,}(?:more than )?(\d+) \w+\s+\+(\d+)%\s*$', row)
        if m:
            c.premiums[m[1].strip()] = (int(m[2]), int(m[3]))
    for row in sections[{1:8,3:7,4:6}[hospital]].splitlines():
        m = re.match(r'^(.+?)\s{2,}(\d+) \w+\s*$', row)
        if m:
            c.caps[m[1].strip()] = int(m[2])
    for row in sections[{1:6,3:5,4:10}[hospital]].splitlines():
        m = re.match(r'^(.+?)\s{2,}\+(\d+)%\s*$', row)
        if m:
            c.weekends[m[1].strip()] = int(m[2])
    for row in sections[{1:7,3:6,4:8}[hospital]].splitlines():
        if hospital in (1,3):
            m = re.match(r'^(.+?)\s{2,}(?:more than )?(\d+) \w+\s+(\d+)%\s*$', row)
        else:
            m = re.match(r'^(.+?)\s{2,}[^\n]*?\((\d+)\)\s{2,}[^\n]*?\((\d+)%\)\s*$', row)
        if m:
            c.discounts.setdefault(m[1].strip(), []).append((int(m[2]), int(m[3])))
    for row in sections[{1:9,3:8,4:7}[hospital]].splitlines():
        parts = re.split(r'\s{2,}', row.strip())
        if len(parts) == 4:
            a, b, ra, rb = parts if hospital in (1,3) else (parts[0], parts[2], parts[1], parts[3])
            if a in c.services and b in c.services and ra.startswith('GBP ') and rb.startswith('GBP '):
                cents = lambda x: integer(Decimal(x.removeprefix('GBP ').replace(',', '')) * 100)
                c.bundles[a] = (b, cents(ra))
                c.bundles[b] = (a, cents(rb))
    for row in sections[10 if hospital == 1 else 9].splitlines():
        m = re.match(r'^(.+?)\s{2,}(\d+) days\s+(.+?)\s*$', row)
        if m:
            c.exclusions[m[1].strip()] = (int(m[2]), m[3].strip())
    if hospital == 3:
        amendment=(Path(root)/'contracts/hospital_3/amendment_no_1.txt').read_text(encoding='utf-8-sig')
        if f'Contract number: {c.number}' not in amendment:
            raise ValueError('H3 amendment has a different contract number')
        effective=re.search(r'This Amendment takes effect on (\d+ \w+ \d{4})\.',amendment)
        if not effective or 'This Amendment applies by Service Date.' not in amendment:
            raise ValueError('H3 amendment applicability is not recognised')
        c.amendment_date=datetime.strptime(effective[1],'%d %B %Y').date()
        replacements=amendment.split('A1.2 SUBSTITUTED RATES',1)[1].split('A1.3 ADDITIONAL SERVICES',1)[0]
        for row in replacements.splitlines():
            m=re.match(r'^(.+?)\s{2,}(per .+?)\s{2,}GBP ([\d,.]+)\s+GBP ([\d,.]+)\s*$',row)
            if m:
                name,unit,old,new=m.groups();name=name.strip()
                old=integer(Decimal(old.replace(',',''))*100)
                new=integer(Decimal(new.replace(',',''))*100)
                if name not in c.services or c.services[name]['rate'] != old or c.services[name]['unit_text'] != unit.strip():
                    raise ValueError('H3 amendment does not reconcile with Appendix B')
                c.amended_rates[name]=new
        additions=amendment.split('A1.3 ADDITIONAL SERVICES',1)[1].split('A1.4 OTHER TERMS UNAFFECTED',1)[0]
        for row in additions.splitlines():
            m=re.match(r'^(.+?)\s{2,}(per .+?)\s{2,}GBP ([\d,.]+)\s*$',row)
            if m:
                name,unit,amount=m.groups();name=name.strip()
                if name in c.services:
                    raise ValueError('H3 additional service already appears in Appendix B')
                c.services[name]={'unit':UNITS.get(unit.strip()),'unit_text':unit.strip(),
                                  'rate':integer(Decimal(amount.replace(',',''))*100)}
                c.introduced_on[name]=c.amendment_date
        if len(c.amended_rates)!=7 or len(c.introduced_on)!=2:
            raise ValueError('H3 amendment incomplete: expected seven repriced and two added services')
    expected = {1: (108, 9, 7, 7, 7, 6, 6), 3:(120,14,12,12,12,10,10), 4: (98, 18, 18, 0, 3, 14, 15)}[hospital]
    actual = tuple(len(x) for x in (c.services,c.premiums,c.caps,c.weekends,c.discounts,c.bundles,c.exclusions))
    if actual != expected:
        raise ValueError(f'Contract extraction incomplete: {actual}, expected {expected}')
    for rules in [c.premiums,c.caps,c.weekends,c.discounts,c.bundles,c.exclusions]:
        if not set(rules) <= set(c.services):
            raise ValueError('Rule references an unparsed service')
    return c


def map_description(description, contract):
    observed = tokens(description)
    candidates = [s for s in contract.services if observed and observed <= tokens(s)]
    # Inference requires at least two retained words, including a service word.
    # Unique partial matches are explicitly reported, never called exact matches.
    selected = None
    status = 'unresolved'
    if len(candidates) == 1:
        candidate = candidates[0]
        anchors = set(candidate.lower().split()[:2])
        service_words = tokens(candidate) - anchors
        if len(observed) >= 2 and (observed & service_words or anchors <= observed):
            selected = candidate
            status = 'explicit_terms' if anchors <= observed and len(observed) >= 3 else 'unique_partial_inference'
    return selected, status, candidates


def load_records(root, hospital):
    path = Path(root) / 'invoices' / f'hospital_{hospital}_invoices.jsonl'
    invoices, lines = [], []
    with path.open(encoding='utf-8-sig') as stream:
        for pos, raw in enumerate(stream, 1):
            if not raw.strip():
                continue
            invoice = json.loads(raw)
            invoice['record_id'] = pos
            invoice['errors'] = set()
            invoice['review'] = set()
            invoice['items'] = []
            for ordinal, item in enumerate(invoice.pop('line_items'), 1):
                line = dict(item, record_id=pos, ordinal=ordinal, patient_id=invoice['patient_id'],
                            parent_invoice_id=invoice['invoice_id'],parent_invoice_date=invoice['invoice_date'], errors=set(), review=set(),
                            expected=None, expected_rate=None, evidence=[])
                invoice['items'].append(line)
                lines.append(line)
            invoices.append(invoice)
    return invoices, lines


def possible(line, service):
    return line['service'] == service or (line['service'] is None and
        (not line['candidates'] or service in line['candidates']))


def discount_percent(prior, tiers):
    return max([percent for threshold, percent in tiers if prior > threshold] or [0])


def audit(root, hospital):
    c = parse_contract(root, hospital)
    invoices, lines = load_records(root, hospital)
    ids = Counter(i['invoice_id'] for i in invoices)
    line_ids = Counter(l['line_id'] for l in lines)
    patients = defaultdict(list)
    daily = defaultdict(list)
    mapping = {}
    known_words = set().union(*(tokens(s) for s in c.services))
    for line in lines:
        description = line['description']
        if description not in mapping:
            mapping[description] = map_description(description, c)
        line['service'], line['mapping_status'], line['candidates'] = mapping[description]
        line['day'] = parse_date(line['service_date'])
        line['quantity_int'] = None
        try:
            q = integer(line['quantity'])
            if q < 0:
                raise ValueError('negative quantity')
            line['quantity_int'] = q
        except (ValueError, ArithmeticError):
            line['review'].add('quantity_invalid')
        if line_ids[line['line_id']] > 1:
            line['review'].add('duplicate_line_identifier')
        if not line['day']:
            line['errors'].add('malformed_service_date')
            line['review'].add('invalid_service_date')
        elif not c.start <= line['day'] <= c.end:
            line['errors'].add('service_date_out_of_window')
            line['review'].add('out_of_term_date')
        if line['service'] is None:
            line['review'].add('unresolved_service_mapping')
            # Only assert an unlisted service when all observed words belong
            # to the contract vocabulary, yet no contracted name contains them.
            # A typo/unknown word remains review-only. No amount is invented.
            observed = tokens(description)
            if not line['candidates'] and len(observed) >= 3 and observed <= known_words:
                line['errors'].add('unknown_service')
        else:
            unit = c.services[line['service']]['unit']
            if unit is None:
                line['review'].add('ambiguous_contract_unit')
            elif line['unit_basis_as_billed'] != unit:
                line['errors'].add('wrong_unit_basis')
                line['review'].add('unit_conversion_unresolved')
        q = line['quantity_int']
        if q is not None and q * integer(line['unit_price_cents']) != integer(line['line_total_cents']):
            line['errors'].add('line_total_arithmetic')
        patients[line['patient_id']].append(line)
        if line['service'] and line['day']:
            daily[(line['patient_id'],line['day'],line['service'])].append(line)
    # Global cumulative utilisation bounds. Missing service dates or uncertain
    # identities can affect earlier positions; only price when both bounds agree.
    for service, tiers in c.discounts.items():
        relevant = [l for l in lines if possible(l, service)]
        ordered = sorted([l for l in relevant if l['day']], key=lambda l:(l['day'],str(l['line_id'])))
        uncertain = [l for l in relevant if not l['day']]
        lower, upper = 0, sum(l['quantity_int'] or 0 for l in uncertain)
        infinite = any(l['quantity_int'] is None or 'unit_conversion_unresolved' in l['review'] for l in uncertain)
        for line in ordered:
            if line['service'] == service:
                lo = discount_percent(lower, tiers)
                hi = max(p for _,p in tiers) if infinite else discount_percent(upper, tiers)
                line['discount_bounds'] = (lo, hi)
                line['evidence'].append(f'prior_utilisation_bounds={lower}:{"unbounded" if infinite else upper}')
            reliable = line['quantity_int'] is not None and 'unit_conversion_unresolved' not in line['review']
            if not reliable:
                infinite = True
            else:
                upper += line['quantity_int']
                if line['service'] == service:
                    lower += line['quantity_int']
    for line in lines:
        service, day, q = line['service'], line['day'], line['quantity_int']
        if service is None or day is None or q is None:
            continue
        peer = patients[line['patient_id']]
        group = daily[(line['patient_id'],day,service)]
        rate = c.services[service]['rate']
        evidence = line['evidence']
        before_introduction = service in c.introduced_on and day < c.introduced_on[service]
        if c.amendment_date and day >= c.amendment_date and service in c.amended_rates:
            rate=c.amended_rates[service]
            evidence.append('H3 Amendment A1.1-A1.2: revised rate by service date')
        base_rate = rate
        uncertainty = [p for p in peer if p is not line and possible(p, service)
                       and (p['day'] is None or (p['day'] == day and p['service'] is None))]
        if uncertainty:
            line['review'].add('possible_unresolved_same_day_service')
        if len(group) > 1:
            line['review'].add('duplicate_service_allocation_unresolved')
            # The contract forbids repeated same-patient/service/day billing.
            # Mark later records, preserving the first as the candidate original.
            ordered = sorted(group,key=lambda p:(parse_date(p['parent_invoice_date']) or date.max,
                p['parent_invoice_id'],str(p['line_id']),p['ordinal']))
            if line is not ordered[0]:
                kind = 'cross_invoice_duplicate' if line['record_id'] != ordered[0]['record_id'] else 'duplicate_service'
                line['errors'].add(kind)
            evidence.append('H%d section %d: repeated patient/service/day' % (hospital,10 if hospital==3 else 11))
        if service in c.bundles:
            partner, bundled_rate = c.bundles[service]
            exists = any(p['service'] == partner and p['day'] == day for p in peer)
            uncertain_partner = any(possible(p,partner) and
                (p['day'] is None or (p['day'] == day and p['service'] is None)) for p in peer)
            if exists:
                rate = bundled_rate
                evidence.append('bundle_substitution')
            elif uncertain_partner:
                line['review'].add('bundle_partner_unresolved')
        daily_qty = sum(p['quantity_int'] or 0 for p in group)
        bad_group = bool(uncertainty) or any(p['quantity_int'] is None or
            'unit_conversion_unresolved' in p['review'] for p in group)
        payable = q
        if service in c.caps:
            cap = c.caps[service]
            if bad_group:
                line['review'].add('daily_quantity_unresolved')
            elif daily_qty > cap:
                line['errors'].add('daily_cap_exceeded')
                evidence.append(f'daily_quantity={daily_qty};cap={cap}')
                if len(group) == 1:
                    payable = min(q,cap)
                else:
                    line['review'].add('cap_allocation_unresolved')
        premium = 0
        if service in c.premiums:
            threshold, percent = c.premiums[service]
            if bad_group:
                line['review'].add('premium_quantity_unresolved')
            else:
                premium = percent if daily_qty > threshold else 0
                rate = adjusted(rate,premium)
                evidence.append(f'daily_quantity={daily_qty};threshold={threshold};premium={premium}')
        if service in c.weekends:
            uplift = c.weekends[service] if day.weekday() >= 5 else 0
            rate = adjusted(rate,uplift)
            evidence.append(f'weekend_uplift={uplift}')
        discount = 0
        if service in c.discounts:
            low, high = line.get('discount_bounds',(None,None))
            if low is None or low != high:
                line['review'].add('discount_utilisation_unresolved')
            else:
                discount = low
                rate = adjusted(rate,-discount)
                evidence.append(f'volume_discount={discount}')
        if service in c.exclusions:
            window, trigger = c.exclusions[service]
            distances = [abs((p['day']-day).days) for p in peer if p['service'] == trigger and p['day']]
            if any(d < window for d in distances):
                rate = 0
                if integer(line['line_total_cents']) != 0:
                    line['errors'].add('exclusion_window_violation')
                evidence.append(f'exclusion_trigger={trigger};window={window}')
            elif window in distances:
                line['review'].add('exclusion_boundary_unresolved')
            elif any(possible(p,trigger) and (p['day'] is None or
                    (p['service'] is None and abs((p['day']-day).days) <= window)) for p in peer):
                line['review'].add('exclusion_trigger_unresolved')
        # A finding can exist without a complete payable total. Do not replace
        # unresolved totals with billed amounts or a sum of only known lines.
        if before_introduction:
            # A1.3 explicitly makes these services non-billable before the
            # effective date. This is not a guessed zero for unknown services.
            rate=0
            line['errors'].add('service_not_contracted_on_date')
            evidence.append('H3 Amendment A1.3: service not billable before introduction')
        if not line['review']:
            line['expected_rate'] = rate
            line['expected'] = rate * payable
            billed_rate = integer(line['unit_price_cents'])
            if billed_rate != rate and not ({'exclusion_window_violation','service_not_contracted_on_date'} & line['errors']):
                line['errors'].add('unit_price_mismatch')
                if service in c.premiums or service in c.weekends:
                    line['errors'].add('premium_omitted' if billed_rate < rate else 'premium_incorrectly_applied')
                if service in c.discounts:
                    line['errors'].add('volume_discount_omitted' if billed_rate > rate else 'volume_discount_incorrectly_applied')
                if 'bundle_substitution' in evidence and billed_rate > rate:
                    line['errors'].add('bundle_not_applied')
            evidence.append(f'base={base_rate};effective_rate={rate};payable_quantity={payable}')
    invoice_rows = []
    for inv in invoices:
        day = parse_date(inv['invoice_date'])
        if not day:
            inv['errors'].add('malformed_invoice_date')
            inv['review'].add('invalid_invoice_date')
        if ids[inv['invoice_id']] > 1:
            inv['errors'].add('duplicate_invoice_id')
            inv['review'].add('ambiguous_invoice_identifier')
        if inv['contract_number'] != c.number:
            inv['errors'].add('contract_number_mismatch')
        if inv.get('facility_code') != 'F-MAIN':
            inv['review'].add('unsupported_facility')
        if not inv['items']:
            inv['review'].add('missing_items')
        if sum(integer(l['line_total_cents']) for l in inv['items']) != integer(inv['invoice_total_cents']):
            inv['errors'].add('invoice_total_mismatch')
        for line in inv['items']:
            if day and line['day'] and line['day'] > day:
                line['errors'].add('service_date_after_invoice_date')
            inv['errors'].update(line['errors'])
            inv['review'].update(line['review'])
        complete = not inv['review'] and all(l['expected'] is not None for l in inv['items'])
        expected = sum(l['expected'] for l in inv['items']) if complete else None
        if complete and expected != integer(inv['invoice_total_cents']):
            inv['errors'].add('recomputed_total_mismatch')
        inferred = any(l['mapping_status'] == 'unique_partial_inference' for l in patients[inv['patient_id']])
        for own in inv['items']:
            if own['service'] in c.discounts:
                inferred |= any(l['mapping_status'] == 'unique_partial_inference' and
                                possible(l,own['service']) for l in lines)
        invoice_rows.append(dict(record_id=inv['record_id'], invoice_id=inv['invoice_id'],
            detected_errors='|'.join(sorted(inv['errors'])), flagged=int(bool(inv['errors'])),
            expected_total_cents=expected, billed_total_cents=integer(inv['invoice_total_cents']),
            pricing_complete=int(complete), review_reasons='|'.join(sorted(inv['review'])),
            mapping_inference_exposed=int(inferred)))
    line_rows = []
    for line in lines:
        line_rows.append(dict(record_id=line['record_id'], invoice_id=line['parent_invoice_id'],
            line_id=line['line_id'],patient_id=line['patient_id'],service_date=line['service_date'],
            description=line['description'],contract_service=line['service'] or '',
            mapping_status=line['mapping_status'],candidate_services='|'.join(line['candidates']),
            quantity=line['quantity'],unit_basis_as_billed=line['unit_basis_as_billed'],
            unit_price_cents=line['unit_price_cents'],line_total_cents=line['line_total_cents'],
            expected_rate_cents=line['expected_rate'],expected_line_total_cents=line['expected'],
            detected_errors='|'.join(sorted(line['errors'])),review_reasons='|'.join(sorted(line['review'])),
            evidence='; '.join(line['evidence'])))
    return invoice_rows,line_rows,c


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    from run import main
    main()
