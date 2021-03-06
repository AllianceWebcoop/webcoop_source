
from odoo import models, fields, api, _
from odoo.exceptions import Warning, ValidationError, UserError
import odoo.addons.decimal_precision as dp
from datetime import datetime
from dateutil.relativedelta import relativedelta
import math
import logging
from pickle import FALSE
#from util import *

_logger = logging.getLogger(__name__)
DF = "%Y-%m-%d"
EPS = 0.00001

#IMPLEMENTATION = True

class Loan(models.Model):
    _inherit = "wc.loan"
    
#     is_made_schedule=fields.Boolean(default=False,
#                                     help="this is internal flag. if this flag is off , schedule will be made before saving")
    
    is_necessary_making_schedule = fields.Boolean(default=False,
                                    help="this is internal flag.If flag is on, this is during making schedule.")
    
    
#     is_skip_making_schedule=fields.Boolean(default=False,compute="compute_is_skip_making_schedule")


    
#     @api.multi
#     @api.constrains('is_made_schedule')
#     def _check_is_made_schedule(self):
#         for r in self:
# #             if r.amortizations and not r.is_made_schedule:
#             if r.is_made_schedule:
#                 r.generate_schedule()
#                 raise ValidationError(_("Repayment schedule was changed.Please confirm it first."))



#     @api.multi
#     @api.constrains('is_made_schedule')
#     def _check_is_made_schedule(self):
#         for r in self:
#             if not r.is_made_schedule:
#                 r.generate_schedule()
# #                 raise ValidationError(_("Repayment schedule was changed.Please confirm it first."))

    @api.multi
    def generate_schedule(self):
        for loan in self:
            if loan.state=='draft':
                ndate = self.get_first_open_date()
                if loan.date!=ndate:
                    if loan.editable_date and loan.date:
                        if loan.date>=self.env.user.company_id.start_date:
                            loan.date = ndate
                            #raise ValidationError(_("Approval date should be equal to open posting date or prior to beginning date."))
                    else:
                        loan.date = ndate
                _logger.debug("gen sched: date=%s", loan.date)        
        
            if loan.is_interest_epr:
                loan.generate_amortization_straight_interest()
#                 loan.term_payments = len(loan.amortizations)
                if loan.is_interest_deduction_first:
                    loan.recompute_update_advance_interest()
            else:
#                 super(Loan, loan).generate_amortization_simple_interest(round_to_peso=True)
                loan.generate_amortization_simple_interest(round_to_peso=True)

#             loan.is_made_schedule =True
        

    
    @api.onchange('maturity',
        'loan_type_id',
        'maturity_period',
        'date_start',
        'amount',
        'payment_schedule',
        'payment_schedule_xdays',
        'is_interest_deduction_first',
        'bulk_principal_payment',
        'interest_rate',
        'is_fixed_payment_amount',
        'days_in_year')
    def onchange_for_regenerate_schedule(self):
        self.ensure_one()
        loan = self
        if loan.maturity and loan.maturity_period and \
               loan.date_start and (loan.amount >0) and \
               (loan.term_payments >0) and loan.payment_schedule:
#             if (loan.payment_schedule =='xdays' and loan.payment_schedule_xdays>0) or \
#                 (loan.payment_schedule !='xdays'):
            if (loan.payment_schedule =='x-days' and loan.payment_schedule_xdays>0) or \
                (loan.payment_schedule !='x-days'):
                return {'value':{'is_necessary_making_schedule':True}}
                        
#                 self.is_necessary_making_schedule = True   
                   

    
#     @api.multi
#     @api.depends('maturity',
#         'maturity_period',
#         'date_start',
#         'amount',
#         'payment_schedule',
#         'payment_schedule_xdays',
#         'term_payments')  
#     def compute_is_skip_making_schedule(self):
#         for loan in self:
#             self.is_skip_making_schedule = True
#             if loan.maturity and loan.maturity_period and \
#                loan.date_start and (loan.amount >0) and \
#                (loan.term_payments >0) and loan.payment_schedule:
#                if (loan.payment_schedule =='xdays' and loan.payment_schedule_xdays>0) or \
#                   (loan.payment_schedule !='xdays'):
#                   self.is_skip_making_schedule = False

                           
            

    
    
    
    @api.multi
    def write(self, vals):
        res = super(Loan, self).write(vals)

        for loan in self:
            if 'is_necessary_making_schedule' in vals and vals['is_necessary_making_schedule']:
                loan.is_necessary_making_schedule = False
                loan.generate_schedule()
                #b606 del 20191218
                #loan.recompute_update_advance_interest()
            if loan.is_necessary_making_schedule:
                loan.is_necessary_making_schedule = False

        return res

        
    @api.model
    def create(self, vals):
        res = super(Loan, self).create(vals)
        if res.maturity and res.maturity_period and \
           res.date_start and (res.amount >0) and \
           (res.term_payments >0) and res.payment_schedule:
#            if (res.payment_schedule =='xdays' and res.payment_schedule_xdays>0) or \
#               (res.payment_schedule !='xdays'):
           if (res.payment_schedule =='x-days' and res.payment_schedule_xdays>0) or \
              (res.payment_schedule !='x-days'):
               res.is_necessary_making_schedule = False
               res.generate_schedule()
        if res.is_necessary_making_schedule:
            res.is_necessary_making_schedule = False


        return res
        



    
    @api.multi
    @api.depends(
        'maturity',
        'maturity_period',
        'date_start',
        'payment_schedule',
        'payment_schedule_xdays'
        #'is_360_day_year'
    )
    def compute_date_maturity(self):
        for rec in self:
            if rec.date_start == False or rec.maturity_period == False :
                rec.date_maturity = False
                rec.term_payments = False
                return

            rec.date_maturity  = rec.get_date_maturity()
            rec.term_payments = rec.get_term_payments()            
    
    
    def get_term_payments(self):
        self.ensure_one()
        #get term_payments 
        n = self.get_term_payments_simple()
        loan = self
        
        #minus skip date count , if the schedule is daily and straight interest
        if n > 0 and loan.is_interest_epr and loan.payment_schedule == 'day':
            skip_days = [6]
            if loan.loan_type_id.skip_saturday:
                skip_days.append(5)

            skip_dates = set(self.get_skip_dates(loan.date_start))
            n -= self.get_skipdate_count(skip_days,skip_dates)
        return n

#util for loan schedule    
    def get_skipdate_count(self,skip_days=[6],skip_dates=[]):
                
        self.ensure_one()
        d0 = fields.Datetime.from_string(self.date_start)
        dend = fields.Datetime.from_string(self.date_maturity)

        if not d0 or not dend:
            return

        if self.loan_type_id.skip_saturday:
            skip_days.append(5)
        
        dn = d0
        n = 0
#         while dn < dend:
        while dn <= dend:
            if dn.weekday() in skip_days or dn in skip_dates:
                n+=1
            dn += relativedelta(days=1)
        return n

#util for loan schedule     
    def get_date_maturity(self):
            self.ensure_one()
            rec = self

            if rec.date_start:
                dt0 = fields.Datetime.from_string(rec.date_start)
                if rec.maturity_period=='months':
                    dt = dt0 + relativedelta(months=rec.maturity)                    
                    return dt.strftime(DF)
                elif rec.maturity_period=='days':
                    dt = dt0 + relativedelta(days=rec.maturity)
                    return dt.strftime(DF)
                elif rec.maturity_period=='weeks':
                    dt = dt0 + relativedelta(days=7*rec.maturity)
                    return dt.strftime(DF)

            return False
    
#util for loan schedule     
    def get_term_payments_simple(self):
            self.ensure_one()
            rec = self
            n=0
            if rec.date_start:
                dt0 = fields.Datetime.from_string(rec.date_start)
                dt = fields.Datetime.from_string(rec.date_maturity)
                days = (dt - dt0).days
                if rec.maturity_period=='months':
                    if (rec.payment_schedule=='day'):
                        n = days
                    elif (rec.payment_schedule=='week'):
                        n = math.ceil(days/7.0)
                    elif (rec.payment_schedule=='half-month'):
                        n = rec.maturity * 2
                    elif (rec.payment_schedule=='15-days'):
                        n = math.ceil(days/15.0)
                    elif (rec.payment_schedule=='month'):
                        n = rec.maturity
                    elif (rec.payment_schedule=='30-days'):
                        n = math.ceil(days/30.0)
                    elif (rec.payment_schedule=='quarter'):
                        n = math.ceil(rec.maturity/3.0)
                    elif (rec.payment_schedule=='semi-annual'):
                        n = math.ceil(rec.maturity/6.0)
                    elif (rec.payment_schedule=='year'):
                        n = math.ceil(rec.maturity/12.0)
                    else:
                        n = 1
                elif rec.maturity_period=='days' or rec.maturity_period =='weeks':
                    if (rec.payment_schedule=='day'):
                        n = days
                    elif (rec.payment_schedule=='week'):
                        n = math.ceil(days/7.0)
                    elif (rec.payment_schedule=='half-month'):
                        #n = math.ceil(rec.maturity/15.2083334)
                        n = math.ceil(days * 24.0 / 365.0)
                    elif (rec.payment_schedule=='15-days'):
                        n = math.ceil(days/15.0)
                    elif (rec.payment_schedule=='month'):
                        n = math.ceil(days * 12.0 / 365.0)
                    elif (rec.payment_schedule=='30-days'):
                        n = math.ceil(days/30.0)
                    elif (rec.payment_schedule=='quarter'):
                        n = math.ceil(days/91.25)
                    elif (rec.payment_schedule=='semi-annual'):
                        n = math.ceil(days/182.5)
                    elif (rec.payment_schedule=='year'):
                        n = math.ceil(days/365.0)
                    else:
                        n = 1
                if rec.payment_schedule == 'x-days' and rec.payment_schedule_xdays > 0:        
                    n = math.ceil(days/float(rec.payment_schedule_xdays))                
            return n
        
    @api.multi
    @api.depends('payment_schedule','date_start','payment_schedule_xdays')
    def compute_date_first_due(self):
        super(Loan,self).compute_date_first_due()


#refactoring on 20191101
    @api.multi
    def generate_amortization_simple_interest(self, round_to_peso=True):
 
         for loan in self:
             if loan.state == 'draft': # and loan.term_payments>0:
                _logger.debug("Simple interest: %s", loan)
                #delete details first
                self.details.unlink()
                self.amortizations.unlink()
# refactor by  get_loan_schedules_for_deminishing module                
#                  tbalance = loan.amount
#  
#                  try:
#                      days_in_year = float(loan.days_in_year)
#                  except:
#                      days_in_year = 365.0
#  
#                  d1 = fields.Datetime.from_string(loan.date_start)
#                  d0 = d1
#                  dend = fields.Datetime.from_string(loan.date_maturity)
#                  i = 1
#  
#                  payments = loan.term_payments
#                  principal_due = 0.0
#  
#                  default_principal_due = round(loan.amount / payments, 2)
#  
#                  if loan.interest_rate == 0.0:
#                      c = default_principal_due
#                  else:
#                      d2, days = self.get_next_due(d1, loan.payment_schedule, i, d0, loan=loan)
#                      r = loan.interest_rate * days / (days_in_year * 100.0)
#                      c = loan.amount * r / (1.0 - 1.0 / ((1+r)**payments))
#                      if round_to_peso:
#                          c = math.ceil(c)
#  
#                  lines=[]
#                  
#                  for i in range(1, loan.term_payments):
#                      d2, dx = self.get_next_due(d1, loan.payment_schedule, i, d0, loan=loan)
#                      days = (d2 - d1).days
#                      #interest_due = round(tbalance * loan.interest_rate * days / (days_in_year * 100.0), 2)
#                      interest_due = loan.compute_interest(
#                          tbalance,
#                          d1.strftime(DF),
#                          d2.strftime(DF)
#                      )
#                      principal_due = self.compute_principal_due(default_principal_due, interest_due, c)
#                      #if (loan.is_fixed_payment_amount):
#                      #    principal_due = round(c - interest_due, 2)
#                      #else:
#                      #    principal_due = default_principal_due
#  
#                      if principal_due!=0.0 or interest_due!=0.0:
#                          vals = {
#                              'loan_id': loan.id,
#                              'date_start': d1.strftime(DF),
#                              'date_due': d2.strftime(DF),
#                              'name': "Schedule %d" % i,
#                              'days': days,
#                              'principal_balance': tbalance,
#                              'principal_due': principal_due,
#                              'interest_due': interest_due,
#                              'sequence': i,
#                          }
#                          _logger.debug("create vals=%s", vals)
#                          
#                          lines.append(vals)
#  
#                          tbalance = tbalance - principal_due
#  
#                      d0 = d1
#                      d1 = d2
#                      i += 1
#  
#                  days = (dend - d1).days
#                  #interest_due = round(tbalance * loan.interest_rate * days / (days_in_year * 100.0), 2)
#                  interest_due = loan.compute_interest(
#                      tbalance,
#                      d1.strftime(DF),
#                      dend.strftime(DF)
#                  )
#  
#                  vals = {
#                      'loan_id': loan.id,
#                      'date_start': d1.strftime(DF),
#                      'date_due': dend.strftime(DF),
#                      'name': "Schedule %d" % i,
#                      'days': days,
#                      'principal_balance': tbalance,
#                      'principal_due': tbalance,
#                      'interest_due': interest_due,
#                      'sequence': i,
#                  }
#                  _logger.debug("create vals=%s", vals)
#                  ######add#####
#                  lines.append(vals)
#  #                 loan.amortizations.create(vals)

                lines = self.get_loan_schedules_for_deminishing(round_to_peso)
                loan.amortizations = lines


#refactor on 20191101
    @api.multi
    def get_loan_schedules_for_deminishing(self, round_to_peso=True):
        self.ensure_one()
        loan = self
        
        tbalance = loan.amount

        try:
            days_in_year = float(loan.days_in_year)
        except:
            days_in_year = 365.0

        d1 = fields.Datetime.from_string(loan.date_start)
        d0 = d1
        dend = fields.Datetime.from_string(loan.date_maturity)
        i = 1

        payments = loan.term_payments
        principal_due = 0.0

        default_principal_due = round(loan.amount / payments, 2)

        if loan.interest_rate == 0.0:
            c = default_principal_due
        else:
            d2, days = self.get_next_due(d1, loan.payment_schedule, i, d0, loan=loan)
            r = loan.interest_rate * days / (days_in_year * 100.0)
            c = loan.amount * r / (1.0 - 1.0 / ((1+r)**payments))
            if round_to_peso:
                c = math.ceil(c)

        lines=[]
        
        for i in range(1, loan.term_payments):
            d2, dx = self.get_next_due(d1, loan.payment_schedule, i, d0, loan=loan)
            days = (d2 - d1).days
            #interest_due = round(tbalance * loan.interest_rate * days / (days_in_year * 100.0), 2)
            interest_due = loan.compute_interest(
                tbalance,
                d1.strftime(DF),
                d2.strftime(DF)
            )
            principal_due = self.compute_principal_due(default_principal_due, interest_due, c)

            if principal_due!=0.0 or interest_due!=0.0:
                vals = {
                    'loan_id': loan.id,
                    'date_start': d1.strftime(DF),
                    'date_due': d2.strftime(DF),
                    'name': "Schedule %d" % i,
                    'days': days,
                    'principal_balance': tbalance,
                    'principal_due': principal_due,
                    'interest_due': interest_due,
                    'sequence': i,
                }
                _logger.debug("create vals=%s", vals)
                
                lines.append(vals)

                tbalance = tbalance - principal_due

            d0 = d1
            d1 = d2
            i += 1

        days = (dend - d1).days
        #interest_due = round(tbalance * loan.interest_rate * days / (days_in_year * 100.0), 2)
        interest_due = loan.compute_interest(
            tbalance,
            d1.strftime(DF),
            dend.strftime(DF)
        )

        vals = {
            'loan_id': loan.id,
            'date_start': d1.strftime(DF),
            'date_due': dend.strftime(DF),
            'name': "Schedule %d" % i,
            'days': days,
            'principal_balance': tbalance,
            'principal_due': tbalance,
            'interest_due': interest_due,
            'sequence': i,
        }
        _logger.debug("create vals=%s", vals)

        lines.append(vals)
        return lines


#refactoring on 20191101
    @api.multi
    def generate_amortization_straight_interest(self):
        for loan in self:
            if loan.state != 'draft':
                continue

            self.details.unlink()
            self.amortizations.unlink()

            lines = self.get_loan_schedules_for_straight()
            if lines and len(lines)>0:
                self.adjust_loan_schedule_for_straight(lines)
                loan.amortizations = lines
                

#refactoring on 20191101
    def get_loan_schedules_for_straight(self):
        self.ensure_one()
        loan = self
        skip_days = [6]
        if loan.loan_type_id.skip_saturday:
            skip_days.append(5)
        #get holidays
        skip_dates = set(self.get_skip_dates(loan.date_start))

        d1 = fields.Datetime.from_string(loan.date_start)
        d0 = d1
        dend = fields.Datetime.from_string(loan.date_maturity)
        days = (dend - d1).days

        _logger.debug("**gen straight amort 1: %s d1=%s dend=%s days=%s",
            loan.name, d1, dend, days
        )

        lines = []
        n = 0
        while d1 < dend:
            if loan.payment_schedule=='lumpsum':
                d2 = dend
            else:
                d2, dx = self.get_next_due(d1, loan.payment_schedule, n+1, d0, loan=loan)

            d2 = min(d2, dend)
            d2s = d2.strftime(DF)

            #skip sunday if schedule is daily
            if not (loan.payment_schedule=="day" and (d2.weekday() in skip_days or d2s in skip_dates)):
                days = (d2 - d1).days
                n += 1
                lines.append([0, 0, {
                    'loan_id': loan.id,
                    'date_start': d1.strftime(DF),
                    'date_due': d2.strftime(DF),
                    'name': "Schedule %d" % n,
                    'days': days,
                    #'principal_balance': 0,
                    #'principal_due': 0,
                    #'interest_due': 0,
                    'sequence': n,
                }])
            d0 = d1
            d1 = d2
            
        return lines

#refactoring 20191101
    def get_interest_for_straight(self):
        self.ensure_one()
        loan=self
        d1 = fields.Datetime.from_string(loan.date_start)
        d0 = d1
        dend = fields.Datetime.from_string(loan.date_maturity)
        days = (dend - d1).days
        try:
            days_in_year = float(loan.days_in_year)
        except:
            days_in_year = 365.0
            
        if loan.maturity_period=='months' and loan.payment_schedule in ['half-month','month','quarter','semi-annual','year']:
            tinterest = round(loan.amount * loan.interest_rate * loan.maturity / 1200.0, 2)
        else:
            tinterest = round(loan.amount * loan.interest_rate * days / (days_in_year * 100.0), 2)

        n = loan.term_payments
        if loan.loan_type_id.round_to_peso:
            linterest = math.floor(tinterest/n)
        else:
            linterest = math.floor(tinterest * 100 /n)/100
        
        linterest_last = tinterest - linterest*(n-1)
        
        return tinterest, linterest , linterest_last
    

#refactoring 20191101
    def get_principal_for_straight(self):
        self.ensure_one()
        loan=self
        n = loan.term_payments
        round_to_peso = loan.loan_type_id.round_to_peso
        
        if round_to_peso:
            lprincipal = math.floor(loan.amount/n)
        else:
            lprincipal = math.floor(loan.amount * 100 /n)/100

        if loan.bulk_principal_payment:
            lprincipal = 0.0
        
        lprincipal_last = loan.amount - lprincipal*(n-1)
        
        return lprincipal , lprincipal_last
    

#refactoring 20191101
    def adjust_loan_schedule_for_straight(self,lines=False):
        self.ensure_one()
        loan =self
        
        tinterest, linterest , linterest_last  = self.get_interest_for_straight()
        lprincipal , lprincipal_last  = self.get_principal_for_straight()
        
        if lines:
            pbal = loan.amount
            for ln in lines[:-1]:
                ln[2].update({
                    'principal_balance': pbal,
                    'principal_due': lprincipal,
                    'interest_due': linterest,
                })
                pbal -= lprincipal

            lines[-1][2].update({
                'principal_balance': pbal,
                'principal_due': pbal,
                'interest_due': linterest_last,
            })
        
#refactoring on 20191101
#[b606] 
    def adjust_loan_schedule_for_advance_int(self):
        self.ensure_one()
        loan = self
        if not loan.is_interest_epr:
            return
        
        adv_interest_record = False
        if loan.payment_schedule != "day":
            for ded in loan.deduction_ids:
                if ded.code.upper()[:7] != 'ADV-INT' and \
                   ded.code.upper()[:3] == 'ADV' and ded.net_include:
                    if adv_interest_record:
                        raise UserError(_("Cannot define two advance interest deductions at the same time."))
                    adv_interest_record = ded

        if not adv_interest_record:
            return
        
        tinterest, linterest , linterest_last  = loan.get_interest_for_straight()
        
        lines = loan.amortizations
        if len(lines) > 0:
            if adv_interest_record:
                try:
                    ns = adv_interest_record.code[3:].strip()
                    if len(ns)==0:
                        n = 1
                    else:
                        n = int(ns)
                except:
                    n = 1

                nlines = len(lines)
                if n>nlines:
                    n = nlines
                    
                amt = 0.0
                current_line = nlines
                while n>0:
                    line = lines[current_line-1]
                    amt += linterest_last if current_line==nlines else linterest
                    
                    line.interest_due = False
                    current_line -=1
                    n -= 1
                
                adv_interest_record.factor = 0.0
                adv_interest_record.amount = amt

#         if lines:
#             if adv_interest_record:
#                 try:
#                     ns = adv_interest_record.code[3:].strip()
#                     if len(ns)==0:
#                         n = 1
#                     else:
#                         n = int(ns)
#                 except:
#                     n = 1
# 
#                 nlines = len(lines)
#                 if n>nlines:
#                     n = nlines
#                     
#                 amt = 0.0
#                 while n>0:
#                     line = lines[nlines-1][2]
#                     amt += line['interest_due']
#                     line.update({
#                         'interest_due': False,
#                     })
#                     nlines -=1
#                     n -= 1
# 
#                 adv_interest_record.factor = 0.0
#                 adv_interest_record.amount = amt
            # mod end 20191218
            
            