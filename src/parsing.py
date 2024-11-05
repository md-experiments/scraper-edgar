#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Functions for cleaning corporate filings and extracting the MD&A section.

Usage:
    edgar_clean.py clean-filings [--start=INT] [--end=INT] [--form-type=STR]
    edgar_clean.py extract-mda [--start=INT] [--end=INT] [--form-type=STR]
    edgar_clean.py extract-item1 [--start=INT] [--end=INT] [--form-type=STR]

Options:
    -h, --help
    --start=INT                     Start year for scraping [default: 1996].
    --end=INT                       End year for scraping [default: 2020].
    --form-type=STR                 Form type (one of: 8-k, 10-k, 10-k/a, 10-q, 10-q/a) [default: 10-k].

"""


import datetime as dt
import html
import itertools
import re
from pathlib import Path

from docopt import docopt
from tqdm import tqdm

from parsing_patterns import (PAT_10K_MDA1, PAT_10K_MDA2, PAT_10Q_MDA,
                              PAT_ITEM1, PAT_MU1, PAT_MU2, PAT_TAB1, PAT_TAB2,
                              PAT_TOC1, PAT_TOC2)


# define conditional replacement pattern for table-tags (keep if proportion of digits < 10%)
def tab_replace(match, tab_ratio = 0.1):
    """ Helper function to retain text-heavy tables """
    tab_content = match.group(0)
    tab_content = PAT_MU2.sub('\n', tab_content)
    c = len(re.sub('[^A-Za-z]|nbsp', '', tab_content))
    d = len(re.sub('[^0-9]|nbsp', '', tab_content))
    # error handling for ZeroDivisionError
    try:
        num_ratio = d / (c + d)
        if num_ratio < tab_ratio:
            return f'[TABLE]{match.group(0)}[/TABLE]'
        else:
            return ''
    except Exception as e:
        print(type(e).__name__, e)
        return ''

def clean_filing_text(txt: str) -> str:
    
    for v in PAT_MU1.values():
        txt = v.sub('\n', txt)
    txt = html.unescape(txt)
    txt = PAT_TAB1.sub(tab_replace, txt)
    txt = PAT_MU2.sub('\n', txt)
    txt = re.sub(r'\xa0|\u200b', '\n', txt).strip()
    txt = re.sub(r'(\n\s*){3,}', '\n\n', txt).strip()
    return txt

def clean_mda_text(txt: str, form_type: str) -> str:
    """ Clean MD&A section from corporate filing"""
    mda = ''
    txt = PAT_TAB2.sub('', txt)
    # search for matches with MD&A pattern defined above and keep longest match (to omit matches within toc or elsewhere)
    if form_type == '10-k':
        for match in PAT_10K_MDA1.finditer(txt):
            if len(match.group(0)) > len(mda):
                mda = match.group(0)
        for match in PAT_10K_MDA2.finditer(txt):
            if len(match.group(0)) > len(mda):
                mda = match.group(0)
    elif form_type == '10-q':
        for match in PAT_10Q_MDA.finditer(txt):
            if len(match.group(0)) > len(mda):
                mda = match.group(0)
    mda = re.sub(PAT_TOC1, ' ', mda)
    mda = re.sub(PAT_TOC2, ' ', mda)
    mda = re.sub(r'(\_{2,}|\-{2,}|={2,})', ' ', mda)
    mda = re.sub(r'(\s{1,})', ' ', mda)
    mda = re.sub(r' (,|;|\.|’|®) ', r'\1 ', mda)
    mda = re.sub(r'^(.*?)" -->', '', mda)
    return mda

def clean_item1_text(txt: str) -> str:
    item1 = ''
    txt = PAT_TAB2.sub('', txt)
    # search for matches with item1 pattern defined above and keep longest match (to omit matches within toc or elsewhere)
    for match in PAT_ITEM1.finditer(txt):
        if len(match.group(0)) > len(item1):
            item1 = match.group(0)
    item1 = re.sub(PAT_TOC1, ' ', item1)
    item1 = re.sub(PAT_TOC2, ' ', item1)
    item1 = re.sub(r'(\_{2,}|\-{2,}|={2,})', ' ', item1)
    item1 = re.sub(r'(\s{1,})', ' ', item1)
    item1 = re.sub(r' (,|;|\.|’|®) ', r'\1 ', item1)
    item1 = re.sub(r'^(.*?)" -->', '', item1)
    return item1

def clean_filings(start: int, end: int, form_type: str = '10-k'):
    """ Preprocess raw filings
    :param int start:
        Start year for scraping
    :param int start:
        End year for scraping
    :param str form_type:
        Form type (one of: 8-k, 10-k, 10-k/a, 10-q, 10-q/a)
    """

    path_log = Path('output', 'filings', form_type, 'log_parse.txt')
    
    # iterate over all quarters in the start-end period and clean available filings
    for year, qtr in itertools.product(range(start, end + 1), range(1, 4 + 1)):

        path_filings_dir = Path('output', 'filings', form_type, str(year), f'q{str(qtr)}')
        filings = [f for f in path_filings_dir.rglob('*.txt') if not re.search('_', str(f))]

        for filing in tqdm(filings):

            with filing.open('r', encoding='utf-8', errors='ignore') as f:
                txt = f.read()
            
            txt = clean_filing_text(txt)
            with open(filing, 'w', encoding='utf-8', errors='ignore') as f:
                f.write(txt)
            with open(path_log, 'a', encoding='utf-8') as log:
                log.write(f'\n[{dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Cleaning successful! Write to {f.name}'
                          f'\t Length: {len(txt)} chars\n')

    print(f'\nCleaning completed!\n'
          f'Log-file written to {path_log}')



def extract_mda(start: int, end: int, form_type: str = '10-k'):
    """ Extract MD&A section from corporate filing
    :param int start:
        Start year for scraping
    :param int start:
        End year for scraping
    :param str form_type:
        Form type (one of: 8-k, 10-k, 10-k/a, 10-q, 10-q/a)
    """

    path_log = Path('output', 'filings', form_type, 'log_extract_mda.txt')

    for year, qtr in itertools.product(range(start, end + 1), range(1, 4 + 1)):

        path_filings_dir = Path('output', 'filings', form_type, str(year), f'q{str(qtr)}')
        filings = [f for f in path_filings_dir.rglob('*.txt') if not re.search('_', str(f))]

        for filing in tqdm(filings):

            path_mda = Path(filing.parent, f'{filing.stem}_mda.txt')
            if not path_mda.exists():
                with filing.open('r', encoding='utf-8', errors='ignore') as f:
                    txt = f.read()

                mda = clean_mda_text(txt, form_type)

                with path_mda.open('w', encoding='utf-8') as f:
                    f.write(mda)
                with path_log.open('a', encoding='utf-8') as f:
                    f.write(f'\n[{dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] MD&A extraction successful! Write to {path_mda}'
                            f'\t Length: {len(mda)} chars\n')

    print(f'\nExtraction completed!\n'
          f'Log-file written to {path_log}\n')


def extract_item1(start: int, end: int, form_type: str = '10-k'):
    """ Extract Item 1 section from corporate filing
    :param int start:
        Start year for scraping
    :param int start:
        End year for scraping
    :param str form_type:
        Form type (one of: 8-k, 10-k, 10-k/a, 10-q, 10-q/a)
    """

    path_log = Path('output', 'filings', form_type, 'log_extract_item1.txt')

    for year, qtr in itertools.product(range(start, end + 1), range(1, 4 + 1)):

        path_filings_dir = Path('output', 'filings', form_type, str(year), f'q{str(qtr)}')
        filings = [f for f in path_filings_dir.rglob('*.txt') if not re.search('_', str(f))]

        # iterate over all available filings in quarter
        for filing in tqdm(filings):

            path_item1 = Path(filing.parent, f'{filing.stem}_item1.txt')
            if not path_item1.exists():
                with filing.open('r', encoding='utf-8', errors='ignore') as f:
                    txt = f.read()
                item1 = clean_item1_text(txt)

                with path_item1.open('w', encoding='utf-8') as f:
                    f.write(item1)
                with path_log.open('a', encoding='utf-8') as f:
                    f.write(f'\n[{dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Item 1 extraction successful! Write to {path_item1}'
                            f'\t Length: {len(item1)} chars\n')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Clean and extract corporate filings')
    parser.add_argument('--clean-filings', action='store_true', help='Clean filings')
    parser.add_argument('--extract-mda', action='store_true', help='Extract MD&A section')
    parser.add_argument('--extract-item1', action='store_true', help='Extract Item 1 section')
    parser.add_argument('--start', type=int, default=1996, help='Start year for scraping')
    parser.add_argument('--end', type=int, default=2020, help='End year for scraping')
    parser.add_argument('--form-type', type=str, default='10-k', help='Form type (one of: 8-k, 10-k, 10-k/a, 10-q, 10-q/a)')
    #args = parser.parse_args()
    args = vars(parser.parse_args())
    if args['clean_filings']:
        clean_filings(int(args['start']), int(args['end']), args['form_type'])
    elif args['extract_mda']:
        extract_mda(int(args['start']), int(args['end']), args['form_type'])
    elif args['extract_item1']:
        extract_item1(int(args['start']), int(args['end']), args['form_type'])
