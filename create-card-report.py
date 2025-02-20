import requests
import csv
import re
import argparse
import configparser
from time import sleep
from datetime import datetime, timedelta, date
import pytz

URI = 'https://api-staging.airwallex.com/api/v1'

config = configparser.ConfigParser()
config.read('report.cfg')

valid_daterange_values = ['yesterday', 'today', 'last_month', 'this_month']

def formatted_daterange(daterange='yesterday', format='%Y-%m-%d', timezone='UTC', include_time=True):
    # Get the timezone object
    tz = pytz.timezone(timezone)
    
    # Get current time in the specified timezone
    now = datetime.now(tz)
    
    if daterange == 'yesterday':
        # Calculate yesterday in the specified timezone
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(1)
        end_date = start_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif daterange == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif daterange == 'last_month':
        first_day_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = first_day_of_this_month - timedelta(microseconds=1)  # last moment of last month
        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)  # first moment of last month
    elif daterange == 'this_month':
        end_date = now
        start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        # Assume daterange is a datetime object, localize it if it's naive
        start_date = end_date = daterange
        if isinstance(daterange, datetime) and daterange.tzinfo is None:
            start_date = end_date = tz.localize(daterange)
    
    # Format the dates with timezone information
    if include_time:
        format = format + 'T%H:%M:%S.%f%z'
    
    start_date_str = start_date.strftime(format)
    end_date_str = end_date.strftime(format)
    
    # Trim microseconds to milliseconds (3 decimal places)
    if include_time:
        start_date_str = start_date_str[:-9] + start_date_str[-6:]  # Remove extra microsecond digits
        end_date_str = end_date_str[:-9] + end_date_str[-6:]  # Remove extra microsecond digits

    return [start_date_str, end_date_str]

def get_login_token():
  token_headers = {
    'Content-Type': 'application/json',
    'x-api-key': config['airwallex']['api_key'],
    'x-client-id': config['airwallex']['client_id']
  }

  r = requests.post(URI + '/authentication/login', headers=token_headers)
  token = r.json()['token']

  return token

def get_transactions(daterange='yesterday', timezone='UTC'):
  transcation_count = 0
  start_date, end_date = formatted_daterange(daterange=daterange, timezone=timezone)
  print('Fetching transcations from {} to {}'.format(start_date, end_date))

  if daterange == 'this_month' or daterange == 'last_month':
    report_filename = 'report-{}.csv'.format(start_date.rsplit('-', 1)[0])
  else:
    report_filename = 'report-{}.csv'.format(start_date.split('T')[0])

  with open(report_filename, 'w', newline='') as file:
    writer = csv.writer(file)
    report_fields = [
        'Transaction Date',
        'Transaction Time',
        'Transaction Type',
        'Transaction ID',
        'Card ID',
        'Card Nickname',
        'Client Data',
        'Status',
        'Billing Amount',
        'Billing Currency',
        'Transaction Amount',
        'Transaction Currency',
        'Masked Card Number',
        'Merchant Name',
        'Merchant City',
        'Merchant Country',
        'Merchant Category Code',
        'Posted Date',
        'Posted Time',
        'Failure Reason',
        'Auth Code',
        'Matched Authorizations',
        'Network Transcation ID'
      ]
    
    writer.writerow(report_fields)

    headers = {
      'Authorization': 'Bearer ' + get_login_token(),
      'Content-Type': 'application/json'
    }

    page_num = 0

    while True:
      payload = {
                  'page_num': page_num,
                  'from_created_at': start_date,
                  'to_created_at': end_date
                }
      
      txn_request = requests.get(URI + '/issuing/transactions', params=payload, headers=headers)
      sleep(0.05)
      print(txn_request.json())
      txn_response = txn_request.json()
      transactions = txn_response['items']
      transcation_count = transcation_count + len(transactions)

      print('Processed page {}'.format(page_num))

      for transaction in transactions:
        transaction_date, transaction_time, *_ = re.split(r'T|,|\.', transaction['transaction_date'])
        posted_date, posted_time, *_ = re.split(r'T|,|\.', transaction['posted_date'])
        failure_reason = transaction.get('failure_reason', '')
        matched_authorizations = ''

        if 'matched_authorizations' in transaction:
          matched_authorizations = ', '.join(transaction['matched_authorizations'])
        
        if 'client_data' not in transaction:
          transaction['client_data'] = ''

        transaction_reformatted = [
            transaction_date,
            transaction_time,
            transaction['transaction_type'],
            transaction['transaction_id'],
            transaction['card_id'],
            transaction['card_nickname'],
            transaction['client_data'],
            transaction['status'],
            transaction['billing_amount'],
            transaction['billing_currency'],
            transaction['transaction_amount'],
            transaction['transaction_currency'],
            transaction['masked_card_number'],
            transaction['merchant']['name'],
            transaction['merchant']['city'],
            transaction['merchant']['country'],
            transaction['merchant']['category_code'],
            posted_date,
            posted_time,
            failure_reason,
            transaction['auth_code'],
            matched_authorizations,
            transaction['network_transaction_id']
        ]
        
        writer.writerow(transaction_reformatted)

      if txn_response['has_more']:
        page_num = page_num + 1
      else:
        print('Processing complete. Transcation count: {}'.format(transcation_count))
        break

def generate_balance_activity_report(daterange='yesterday', timezone='UTC'):
    """
    Generate a balance activity report for the specified date range.
    
    Args:
        daterange (str): Date range for the report ('yesterday', 'this_month', 'last_month')
        timezone (str): Timezone for the report (default 'UTC')
    """
    start_date, end_date = formatted_daterange(daterange=daterange, timezone=timezone, include_time=False)
    print('Generating balance activity report from {} to {}'.format(start_date, end_date))

    # Generate report filename
    if daterange in ['this_month', 'last_month']:
        report_filename = 'balance-activity-{}.csv'.format(start_date.rsplit('-', 1)[0])
    else:
        report_filename = 'balance-activity-{}.csv'.format(start_date.split('T')[0])

    headers = {
        'Authorization': 'Bearer ' + get_login_token(),
        'Content-Type': 'application/json'
    }

    # Create financial report request
    report_payload = {
        "type": "BALANCE_ACTIVITY_REPORT",
        "from_date": start_date,
        "to_date": end_date,
        "file_format": "CSV",
        "file_name": report_filename,
        "time_zone": timezone,
        "transaction_types": ["CARD"]
    }

    # Request report generation
    report_request = requests.post(
        URI + '/finance/financial_reports/create',
        json=report_payload,
        headers=headers
    )
    print(report_request.json())
    report_id = report_request.json()['id']
    print(f'Report generation initiated with ID: {report_id}')

    return report_id
  
def download_balance_activity_report(report_id):
  # Poll for report completion
  max_attempts = 36  # 3 minutes maximum wait time
  attempt = 0

  headers = {
        'Authorization': 'Bearer ' + get_login_token(),
        'Content-Type': 'application/json'
    }
  
  while attempt < max_attempts:
      print(f"{URI}/finance/financial_reports/{report_id}")
      status_response = requests.get(
          f"{URI}/finance/financial_reports/{report_id}",
          headers=headers
      )
      print(status_response.json())
      status = status_response.json()['status']
      file_name = status_response.json()['file_name']
      
      if status == 'COMPLETED':
          # Download report
          report_content = requests.get(
            f"{URI}/finance/financial_reports/{report_id}/content", 
            headers=headers
          )
          with open(file_name, 'wb') as file:
              file.write(report_content.content)
          print(f'Report successfully downloaded to {file_name}')
          break
      
      print(f'Report status: {status}. Waiting...')
      sleep(5)  # Wait 10 seconds before next check
      attempt += 1

  if attempt >= max_attempts:
      print('Report generation timed out')
      return

if __name__ == '__main__':
  arg_desc = 'Generate Card Transaction Report'
  parser = argparse.ArgumentParser(description=arg_desc)
  parser.add_argument('-d', '--daterange', nargs='?', help='specify one of {} \
                      or custom date in YYYY-MM-DD format'.format(str(valid_daterange_values)[1:-1]))
  parser.add_argument('-b', '--balance', action="store_true", help='generate balance activity report')
  parser.add_argument('-tz', '--timezone', nargs='?', help='specify timezone for date range, eg. "UTC", "Asia/Singapore"')
  args = vars(parser.parse_args())

  print(args)

  if args['daterange']:
    if args['daterange'] in valid_daterange_values:
      daterange = args['daterange']
    else:
      try:
          daterange = date.fromisoformat(args['daterange'])
      except ValueError:
          raise ValueError('Invalid daterange value')
  else:
    daterange = 'yesterday'

  if args['timezone']:
    if args['timezone'] in pytz.all_timezones_set:
      timezone = args['timezone']
    else:
      raise ValueError('Invalid timezone value')
  else:
    timezone = 'UTC'

  if args['balance']:
    print('Generating Balance Activity Report')
    report_id = generate_balance_activity_report(daterange, timezone)

  print('Generating Card Transaction Report')
  get_transactions(daterange, timezone)

  if report_id:
    download_balance_activity_report(report_id)

  print('Process complete')
