"""Conservative syntax/known-contract checks, not a semantic proof of instructions."""
import re

PROFILE = {'version':'procedure-checks-v1','max_repairs':1,'target_characters':4000,
           'checks':['length','complete_ending','unfinished_final_step','known_output_conflicts']}


def validate_procedure(body, limit):
    if not isinstance(body,dict) or set(body) != {'editorial_strategy','summary'}:
        return ['Return exactly editorial_strategy and summary.']
    text, summary = body['editorial_strategy'], body['summary']
    if not isinstance(text,str) or not text.strip():
        return ['The procedure must be a nonempty string.']
    errors=[]
    if len(text)>limit:
        errors.append(f'The procedure exceeds {limit} characters; shorten it without truncating.')
    if not isinstance(summary,str) or not summary.strip() or len(summary)>2000:
        errors.append('The summary must be nonempty and at most 2000 characters.')
    end=text.rstrip().rstrip('\"\'”’)]}')
    if not end or end[-1] not in '.!?。！？':
        errors.append('Finish the final sentence with terminal punctuation; the procedure appears unfinished.')
    last=text.strip().splitlines()[-1].strip()
    if re.fullmatch(r'(?:#+\s*|(?:step\s*)?\d+[.):\-]\s*).*:',last,re.I):
        errors.append('The final step/heading has no completed instruction.')
    if re.search(r'\b(?:and|or|the|with|to)\s*[.!?]?$',end,re.I):
        errors.append('The last sentence ends with an unfinished clause.')
    for line in text.splitlines():
        lower=line.lower()
        if re.search(r'\b(?:never|do not|don.t|must not|cannot|no|without|avoid|forbid)\b',lower):
            continue
        if (re.search(r'\b(?:convert|rewrite|return|output|format|insert|create|add)\b',lower)
            and re.search(r'\b(?:numbered list|markdown (?:table|list)|new blocks?|new sections?)\b',lower)):
            errors.append('Page output must remain existing single-line plain-text blocks; remove list/new-block directives.')
        if 'review_flags.' in lower:
            errors.append('review_flags is an array, not an object with nested fields.')
    return list(dict.fromkeys(errors))
