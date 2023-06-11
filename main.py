import PyPDF2
import re, os, sys
import shutil
import argparse
import pathlib


DELIMITER = "~"
pdf_path = ""
password=""
input_path = "./"
output_path = None

def reverse_replace(s, old, new):
  return (s[::-1].replace(old[::-1],new[::-1], 1))[::-1]

# def reverse_replace(s, old, new):
#   li = s.rsplit(old, 1) #Split only once
#   return new.join(li)


def parse_account_types(text, i, parsed):
    accounts = []
    
    while not text[i].startswith("TOTAL"):
        account = {}
        split = text[i].split("ACCOUNT")
        account_type = split[0].strip().lower()
        # account["account_type"] = account_type
        account["balance"] = split[1].replace("INR", "").replace(" 0.00", "").strip()
        parsed[account_type] = account.copy()
        accounts.append(account_type)
        i+=1

    account_numbers = []
    while i != len(text):
        while True:
            #  Statement of transactions in Loan Account 077XXXXXXXXX in INR for the period Feb 01, 2023 - Feb 28, 2023
            match=re.search(r"Statement of transactions in (.*) Account ([0-9]+)", text[i])
            i+=1
            if i == len(text):
               break
            if match:
                account_type = match.group(1).strip().lower()
                # print("account_type: ", account_type)
                account_number = match.group(2).strip().lower()
                # print("account_number: ", account_number)
                while True:
                    # 01-02-2023 Opening Balance 40344.22 Cr
                    match=re.search("Opening Balance ([0-9]+\.[0-9]+)", text[i])
                    i+=1
                    if match:
                        previous_amount = float(match.group(1))
                        transactions = []
                        transaction = ""
                        while True:
                            match=re.findall("Closing Balance", text[i])
                            if match:
                                break
                            else:
                                transaction += " " + text[i]
                                # print(transaction)
                                match = re.search(r".*(Cr|Dr)\s*$", transaction)
                                if match:
                                    match = re.search(r"\s*([0-9]{2}-[0-9]{2}-[0-9]{4})\s*(.*)\s+([0-9]+\.[0-9]+)\s*(Cr|Dr)\s*$", transaction)
                                    # match = re.search(r"\s*([0-9]{2}-[0-9]{2}-[0-9]{4})\s*(.*([a-zA-Z\s]|[0-9]{2}-[0-9]{2}-[0-9]{4})){1}([0-9]+\.[0-9]+)\s+([0-9]+\.[0-9]+)\s*(Cr|Dr)\s*$", transaction)
                                    if not match:
                                       print("Transaction not matched")
                                       print(transaction)
                                       sys.exit(1)
                                    current_amount = float(match.group(3))
                                    difference = current_amount - previous_amount
                                    # if abs(difference)  != match.group(4):
                                    previous_amount = current_amount
                                    deduction_type = "Cr" if difference >=0 else "Dr"
                                    # Round off and convert to string
                                    difference = "%.2f" % round(abs(difference), 2) 
                                    # description = match.group(2).strip().replace(difference, "")
                                    description = reverse_replace(match.group(2).strip(), difference, "")
                                    # Form transaction string
                                    transaction = DELIMITER.join([match.group(1), description,
                                                                  difference, match.group(3),
                                                                  deduction_type])
                                    transactions.append(transaction.strip())
                                    transaction = ""
                                i+=1
                        parsed[account_number] = {}
                        parsed[account_number]["transactions"] = transactions
                        parsed[account_number]["account_type"] = account_type
                        account_numbers.append(account_number)
                        break
                break
    parsed["account_numbers"] = account_numbers
            
    return accounts, i


# def parse_cash_credit_account_balance(text, i):
#   while not text[i].startswith("CASH CREDIT ACCOUNT"):
#     i+=1
#   return text[i].split("CASH CREDIT ACCOUNT")[-1].strip(), i


#  Statement of transactions in Savings Account 077XXXXXXXXX in INR for the period  Aug 01, 2022 - Aug 31, 2022
# 01-08-2022 Opening Balance 520.22 Cr
# .......
# 31-08-2022 Closing Balance 576.22 Cr



def parse_fields(text, parsed):
    parsed["name"] = text[0]
    address = ""
    for i in range( len(text[1:]) ):
        line = text[i]
        if line.startswith("CUSTOMER ID"):
            parsed["address"] = address.strip()
            parsed["customer_id"] = line.split("-")[-1].strip()
            parsed["period"] = text[i+1].split("from")[-1].strip()
            i+=4
            parsed["account_types"], i = parse_account_types(text, i, parsed)

            break
        else:
            address += line + "\n"



def parse_pdf(pdf_path):
  #create file object variable
  #opening method will be rb
  pdffileobj = open(pdf_path,'rb')
  
  #create reader variable that will read the pdffileobj
  pdfreader = PyPDF2.PdfReader(pdffileobj)

  # Check if the opened file is actually Encrypted
  if pdfreader.is_encrypted:
      # If encrypted, decrypt it with the password
      pdfreader.decrypt(password)

  #This will store the number of pages of this pdf file
  x = len(pdfreader.pages)
  # print(x)

  #create a variable that will select the selected number of pages
  # pageobj=pdfreader.pages[0]

  extracted_text = ""
  for page in pdfreader.pages:
      extracted_text += page.extract_text()
  # print(extracted_text)

  text = extracted_text.split("\n")
  # for line in text:
  #   print(line)
  
  parsed = {}
  parse_fields(text, parsed)
  
  return parsed


def create_output_path(output_path):
  if os.path.exists(output_path):
    shutil.rmtree(output_path)
  os.makedirs(output_path)


def write_transactions_to_file(parsed):
  for account_number in parsed["account_numbers"]:
    transactions = parsed[account_number]["transactions"]
    with open(os.path.join(output_path, account_number+".txt"), "a+") as fp:
        for transaction in transactions:
          fp.write(transaction + "\n") 


def main():

  global output_path

  if os.path.isfile(input_path):

    if not output_path:
      path = pathlib.Path(input_path).parent.absolute()
      output_path = os.path.join(path, "output")
    create_output_path(output_path)

    parsed = parse_pdf(input_path)
    
    for key, value in parsed.items():
        print(key, " : ", value)

    write_transactions_to_file(parsed)

  else:

    onlyfiles = [f for f in os.listdir(input_path) if f.endswith("pdf")]
    if not output_path:
      output_path = os.path.join(input_path, "output")
    create_output_path(output_path)

    for i in range(len(onlyfiles)):
      parsed = parse_pdf(os.path.join(input_path,onlyfiles[i]))

      for key, value in parsed.items():
        print(key, " : ", value)

      write_transactions_to_file(parsed)
      

# loan, savings, cash credit 


if __name__ == "__main__":

  # print(sys.argv[1:])
  argParser = argparse.ArgumentParser()

  argParser.add_argument("-i", "--input_path", help="input path")
  argParser.add_argument("-o", "--output_path", help="output path")
  argParser.add_argument("-p", "--password", help="password")
  argParser.add_argument("-d", "--delimiter", help="delimiter")

  args = argParser.parse_args()
  # print("args=%s" % args)

  if args.output_path:
    output_path = os.path.join(args.output_path, "output")
  if args.input_path:
    input_path = args.input_path
  if args.password:
    password = args.password
  if args.delimiter:
    DELIMITER = args.delimiter
  
  main()