'''
Created on Mar 9, 2014

@author: Gregory Kramida
@license: GNU v3
@copyright: (c) Gregory Kramida 2014
'''

import sys
import time

def query_yes_no(question, default="yes"):
    """
    Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is one of "yes" or "no".
    Excluded from copyright
    Source: http://code.activestate.com/recipes/577058/
    """
    valid = {"yes":True,   "y":True,  "ye":True,
             "no":False,     "n":False}
    if default == None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "\
                             "(or 'y' or 'n').\n")

def print_progress(i_item, n_items, start_time, items_name = "items"):
    elapsed = time.time() - start_time
    n_done = i_item+1
    frac_done = float(n_done) / n_items
    total_time = elapsed / frac_done
    eta = total_time - elapsed
    hour_eta = int(eta) / 3600
    min_eta = int(eta-hour_eta*3600) / 60
    sec_eta = int(eta-hour_eta*3600-min_eta*60)
    print '{0:.3%} done ({1:0} of {2:0} {3:s}), elapsed: {4:0} eta: {5:0} h {6:0} m {7:0} s'\
.format(frac_done,
        i_item,
        n_items, 
        items_name, 
        int(elapsed), 
        hour_eta,
        min_eta,
        sec_eta),
    sys.stdout.flush()
    print "\r",


CURSOR_UP_ONE = '\x1b[1A'
ERASE_LINE = '\x1b[2K'
def erase_line():
    print(CURSOR_UP_ONE + ERASE_LINE)