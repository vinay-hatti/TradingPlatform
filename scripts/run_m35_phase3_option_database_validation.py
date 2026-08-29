import argparse,csv
from datetime import date
from pathlib import Path
from trading_ai.database import SessionLocal
from trading_ai.scanner.options_market_data_quality.service import OptionDatabaseValidationService
from trading_ai.scanner.options_market_data_quality.database_serialization import write_database_validation_csv,write_database_validation_json,write_missing_symbols_csv
def load_symbols(path):
    with Path(path).open(newline='',encoding='utf-8-sig') as h:
        r=csv.DictReader(h);fields=r.fieldnames or [];sk=next((x for x in fields if x.strip().lower()=='symbol'),None);ak=next((x for x in fields if x.strip().lower()=='active'),None)
        if sk is None:raise ValueError(f'CSV must contain symbol column: {path}')
        out=[]
        for row in r:
            if ak:
                a=str(row.get(ak,'')).strip().lower()
                if a and a not in {'1','true','yes','y'}:continue
            s=str(row.get(sk,'')).strip().upper()
            if s:out.append(s)
    return sorted(set(out))
def main():
    p=argparse.ArgumentParser();p.add_argument('--canonical-csv',default='data/universe/us_listed_equities_etfs.csv');p.add_argument('--quote-date-start',required=True);p.add_argument('--quote-date-end',required=True);p.add_argument('--minimum-expiration-date');p.add_argument('--maximum-expiration-date');p.add_argument('--output-directory',default='reports/m35/phase3/database_validation');a=p.parse_args()
    session=SessionLocal()
    try:profile=OptionDatabaseValidationService(session).evaluate(load_symbols(a.canonical_csv),date.fromisoformat(a.quote_date_start),date.fromisoformat(a.quote_date_end),date.fromisoformat(a.minimum_expiration_date) if a.minimum_expiration_date else None,date.fromisoformat(a.maximum_expiration_date) if a.maximum_expiration_date else None)
    finally:session.close()
    out=Path(a.output_directory);jp=write_database_validation_json(profile,out/'option_database_validation.json');cp=write_database_validation_csv(profile,out/'option_database_validation.csv');mp=write_missing_symbols_csv(profile,out/'missing_option_symbols.csv')
    print('='*70);print('Milestone 35 Phase 3 Historical Option Database Validation');print('='*70)
    for l,v in [('Canonical Symbols',profile.canonical_symbol_count),('Symbols With Records',profile.symbols_with_records),('Missing Symbols',len(profile.missing_symbols)),('Input Records',profile.input_record_count),('Unique Records',profile.unique_record_count),('Duplicate Records',profile.duplicate_record_count),('Valid Records',profile.valid_record_count),('Invalid Records',profile.invalid_record_count),('Records With Warnings',profile.warning_record_count)]:print(f'{l:<32}{v:>12}')
    print(f'JSON Report                    {jp}');print(f'Validation CSV                 {cp}');print(f'Missing Symbols CSV            {mp}')
if __name__=='__main__':main()
