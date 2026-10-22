"""Small synthetic X12 segment demonstration, not a production X12 validator.

837 CLM and 835 CLP fields round-trip our synthetic claim IDs and money.
Envelopes and implementation-guide conformance are intentionally out of scope.
"""
from decimal import Decimal


def submission_segment(claim):
    return f"CLM*{claim['claim_id']}*{Decimal(str(claim['billed_amount'])):.2f}***11:B:1*Y*A*Y*Y~"


def remittance_segment(claim):
    status={'paid':'1','partial':'1','denied':'4','pending':'2'}[claim['claim_status']]
    return f"CLP*{claim['claim_id']}*{status}*{Decimal(str(claim['billed_amount'])):.2f}*{Decimal(str(claim['paid_amount'])):.2f}*0*CI~"


def parse_segments(text):
    output=[]
    for segment in text.strip().split('~'):
        parts=segment.strip().split('*')
        if parts[0]=='CLM':
            if len(parts)<3:raise ValueError('Truncated CLM')
            output.append(dict(transaction='837',claim_id=parts[1],billed_amount=Decimal(parts[2])))
        elif parts[0]=='CLP':
            if len(parts)<5:raise ValueError('Truncated CLP')
            output.append(dict(transaction='835',claim_id=parts[1],status_code=parts[2],billed_amount=Decimal(parts[3]),paid_amount=Decimal(parts[4])))
        elif segment.strip():raise ValueError('Unsupported synthetic segment: '+parts[0])
    return output
