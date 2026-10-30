# -*- coding: utf-8 -*-
"""
Created on Thu Jun  8 16:16:13 2023

@author: meime
"""

import pandas as pd

class tax_rev:
    def __init__(self, EXOG_VARS, tax_cou, bta=0):
        self.ENERGY = EXOG_VARS.E
        self.ENERGY_LIST = self.ENERGY['Lfd_Nr'].to_list()

        self.hh_ener = EXOG_VARS.HH_BASE.loc[:, :, self.ENERGY_LIST]

        self.IND_BASE = EXOG_VARS.IND_BASE.reset_index()
        
        self.hh_ener_idx = self.hh_ener.index
        self.bta = bta

    def load_dynamic(self, vars_):
        self.common = {}
        for k,v in vars_.items():
            self.common[k] = v
    
    def calc_tax_rev_base(self, tax_rate):
        tax_rate = tax_rate.astype({'PROD_COMM':'int64','TRAD_COMM':'int64'})
        tax_rev_base = self.IND_BASE[['REG_imp','PROD_COMM','REG_exp','TRAD_COMM','z_bp']].merge(tax_rate, how='left', on=["REG_imp", "PROD_COMM", "TRAD_COMM","REG_exp"])
        tax_rev_base = tax_rev_base.merge(self.common['price_index'].rename(columns={'PROD_COMM':'TRAD_COMM','REG_imp':'REG_exp'}), how='left')
        tax_rev_base['delta_tax'].fillna(0, inplace=True)
        tax_rev_base["tax_rev_base"] = tax_rev_base["z_bp"] * tax_rev_base["delta_tax"] * tax_rev_base['price_index']

        self.tax_rev_base = tax_rev_base.reset_index().set_index(['REG_imp','PROD_COMM','REG_exp','TRAD_COMM'])
        self.tax_rev_base = self.tax_rev_base[['tax_rev_base']]
        
        return self.tax_rev_base
    
    def calc_tax_rev_prod_base(self, tax_rev_base):
        tax_rev_prod_base = tax_rev_base.groupby(["REG_imp","PROD_COMM"])["tax_rev_base"].sum()
        tax_rev_prod_base = tax_rev_prod_base.to_frame()
        tax_rev_prod_base = tax_rev_prod_base.rename(
            columns={"tax_rev_base": "tax_rev_prod_base"})

        self.tax_rev_prod_base = tax_rev_prod_base

        return self.tax_rev_prod_base
    
    def calc_tax_rev_hh_base(self, tax_rate_hh):

        tax_rate_hh = tax_rate_hh.astype({'TRAD_COMM':'str'})
        hh_ener = self.hh_ener.reset_index().astype({'TRAD_COMM':'str'})

        tax_rev_hh_base = hh_ener.merge(tax_rate_hh[tax_rate_hh['PROD_COMM']=='FD_1'].drop(columns=['PROD_COMM']), how='left', on=["REG_imp", "TRAD_COMM", "REG_exp"])
        tax_rev_hh_base['delta_tax_hh'].fillna(0, inplace=True)
        
        tax_rev_hh_base["tax_rev_hh_base"] = tax_rev_hh_base["VIPA"] * tax_rev_hh_base["delta_tax_hh"]
        
        self.tax_rev_hh_base = tax_rev_hh_base.loc[:,["tax_rev_hh_base"]]
        self.tax_rev_hh_base = self.tax_rev_hh_base.set_index(self.hh_ener_idx)

        return self.tax_rev_hh_base
    
    # def calc_tax_rev_hh(self, tax_rate_hh, hh_ener=None):
    #     if type(hh_ener) != pd.DataFrame:
    #         hh_ener = self.hh_ener
    #         hh_ener_idx = self.hh_ener_idx
    #     else:
    #         hh_ener_idx = hh_ener.index

    #     tax_rate_hh = tax_rate_hh.astype({'TRAD_COMM':'str'})
    #     hh_ener = hh_ener.reset_index().astype({'TRAD_COMM':'str'})
            
    #     tax_rev_hh = hh_ener.merge(tax_rate_hh[tax_rate_hh['PROD_COMM']=='FD_1'].drop(columns=['PROD_COMM']), how='left', on=["REG_imp", "TRAD_COMM", "REG_exp"])
        
    #     tax_rev_hh["tax_rev_hh"] = tax_rev_hh["VIPA"] * tax_rev_hh["delta_tax_hh"]
        
    #     self.tax_rev_hh = tax_rev_hh.loc[:,["tax_rev_hh"]]
    #     self.tax_rev_hh = self.tax_rev_hh.set_index(hh_ener_idx)
        
    #     return self.tax_rev_hh

    def subtract_prev(self, recyc_rev, recyc_prev, infl=None):
        recyc_prev_ = recyc_prev.copy().reset_index()
        recyc_prev_.columns = ["{}_prev".format(x) if x != 'REG_imp' else x for x in recyc_prev_.columns]
        # ! revenues are nominal but the delta is deflated by the CURRENT price level
        # ! downstream (HH/gov/inv); a purely nominal difference therefore leaves an
        # ! inflation residual that keeps accumulating in the demand stocks
        # ! -> express last year's revenue at current prices before differencing
        if infl is not None:
            recyc_prev_ = recyc_prev_.merge(infl, how='left', on=['REG_imp'])
            recyc_prev_['infl'] = recyc_prev_['infl'].fillna(1.0)
            for col in ['recyc_govt_base_prev', 'recyc_inc_base_prev', 'recyc_payr_base_prev', 'recyc_inv_base_prev']:
                recyc_prev_[col] = recyc_prev_[col] * recyc_prev_['infl']
            recyc_prev_ = recyc_prev_.drop(columns=['infl'])
        df = recyc_rev.reset_index().merge(recyc_prev_, how='left', on=['REG_imp']).fillna(0)
        df['recyc_govt_base'] = df['recyc_govt_base'] - df['recyc_govt_base_prev']
        df['recyc_inc_base'] = df['recyc_inc_base'] - df['recyc_inc_base_prev']
        df['recyc_payr_base'] = df['recyc_payr_base'] - df['recyc_payr_base_prev']
        df['recyc_inv_base'] = df['recyc_inv_base'] - df['recyc_inv_base_prev']

        recyc_rev_nat = df[['REG_imp','recyc_govt_base','recyc_inc_base','recyc_payr_base','recyc_inv_base']].copy()
        recyc_rev_nat = recyc_rev_nat.set_index(['REG_imp'])

        return recyc_rev_nat
    
    def calc_recyc_rev(self, tax_rev, rev_split, rev_subtract_exp_base=None):

        rev_split = rev_split[~rev_split['REG_imp'].isna()]
        
        # ? keep in mind this is all nominal!!!
        # ! also keep in mind that the revenue that we keep track should be ONLY change from last year
        # ! hence need to subtract last year's values
        
        # rev_subtract_exp_base = rev_subtract_exp_base.reset_index().groupby(['REG_exp']).agg({'rev_subtract_exp_base':'sum'}).reset_index()
        # rev_subtract_exp_base = rev_subtract_exp_base.rename(columns={'REG_exp':'REG_imp'})

        recyc_rev_nat = tax_rev
        # recyc_rev_nat = tax_rev.merge(rev_subtract_exp_base, how='outer', on=['REG_imp'])
        recyc_rev_nat = recyc_rev_nat.merge(rev_split, how="left", on=["REG_imp"])

        # recyc_rev_nat["net_tax_rev_nat_base"] = (
        #     recyc_rev_nat["tax_rev"].fillna(0) )
            # - recyc_rev_nat["rev_subtract_exp_base"].fillna(0))

        recyc_rev_nat["recyc_govt_base"] = recyc_rev_nat["tax_rev"] * recyc_rev_nat["govt_spend"] # done
        recyc_rev_nat["recyc_inc_base"] = recyc_rev_nat["tax_rev"] * recyc_rev_nat["inc_tax"] # done
        recyc_rev_nat["recyc_payr_base"] = recyc_rev_nat["tax_rev"] * recyc_rev_nat["payr_tax"]
        # ! payroll is NOT working as of 4/16/2025 [BKD]
        recyc_rev_nat["recyc_inv_base"] = recyc_rev_nat["tax_rev"] * recyc_rev_nat["pub_inv"] # done
        
        recyc_rev_nat = recyc_rev_nat.set_index(["REG_imp"])

        self.recyc_rev_nat = recyc_rev_nat.loc[
            :, ["recyc_govt_base", "recyc_inc_base", "recyc_payr_base", "recyc_inv_base"]]
        
        return self.recyc_rev_nat
        
    # def calc_recyc_rev(self, tax_rev_prod, tax_rev_hh, rev_subtract_exp, rev_split):
    #     # tax_rev_prod = self.tax_rev_prod
    #     tax_rev_prod = tax_rev_prod.reset_index(level="PROD_COMM", drop=False)
        
    #     tax_rev_nat = tax_rev_prod.groupby(
    #         ["REG_imp"])["tax_rev_prod"].sum().to_frame().rename(
    #             columns={"tax_rev_prod": "tax_rev_nat"})
        
    #     tax_rev_hh_nat = tax_rev_hh.groupby(
    #         ["REG_imp"])["tax_rev_hh"].sum().to_frame()
        
    #     rev_subtract_exp = rev_subtract_exp.reset_index(
    #         level=["REG_exp","TRAD_COMM"], drop=True)
    #     rev_subtract_exp = rev_subtract_exp.reset_index(level="PROD_COMM", drop=False)
        
    #     rev_subtract_exp_nat = rev_subtract_exp.groupby(
    #         ["REG_imp"])["rev_subtract_exp"].sum().to_frame().rename(
    #             columns={"rev_subtract_exp": "rev_subtract_exp_nat"})

    #     recyc_rev = tax_rev_nat.merge(rev_subtract_exp_nat, how="left", on=["REG_imp"])
    #     # recyc_rev = tax_rev_nat.copy()
    #     recyc_rev = recyc_rev.merge(tax_rev_hh_nat, how="left", on=["REG_imp"])
    #     recyc_rev = recyc_rev.merge(rev_split, how="left", on=["REG_imp"])
        
    #     recyc_rev["net_tax_rev_nat"] = (
    #         recyc_rev["tax_rev_nat"].fillna(0) + recyc_rev["tax_rev_hh"].fillna(0) - recyc_rev["rev_subtract_exp_nat"].fillna(0))
        
    #     recyc_rev["recyc_govt"] = recyc_rev["net_tax_rev_nat"] * recyc_rev["govt_spend"]
    #     recyc_rev["recyc_inc"] = recyc_rev["net_tax_rev_nat"] * recyc_rev["inc_tax"]
    #     recyc_rev["recyc_payr"] = recyc_rev["net_tax_rev_nat"] * recyc_rev["payr_tax"]
    #     recyc_rev["recyc_inv"] = recyc_rev["net_tax_rev_nat"] * recyc_rev["pub_inv"]
        
    #     recyc_rev = recyc_rev.set_index(["REG_imp"])
        
    #     self.recyc_rev = recyc_rev.loc[
    #         :, ["recyc_govt", "recyc_inc", "recyc_payr", "recyc_inv"]]
        
    #     return self.recyc_rev
        
    def calc_tax_iter_cond(self, old, new):
        # Iter_comment:
        # Collect additional labor income
        dtax = old.merge(new.rename(columns={'emission_cost':'emission_cost_prev'}))
        dtax['emission_cost'] = dtax['emission_cost'] / dtax['emission_cost_prev'] - 1.0
        dtax['emission_cost'].fillna(0, inplace=True)
        dtax = dtax.drop(columns=['emission_cost_prev'])  
        return dtax
    
    def build_tax_rev_result(self, tax_rev_prod, tax_rev_hh):
        tax_rev_hh_final = tax_rev_hh.groupby(["REG_imp"])["tax_rev_hh"].sum().to_frame()
        tax_rev_hh_final["PROD_COMM"] = "finalhhdemand"
        tax_rev_hh_final = tax_rev_hh_final.set_index("PROD_COMM", append=True)
        tax_rev_hh_final.columns = ["tax_rev_prod_base"]

        tax_revenue = pd.concat([tax_rev_prod, tax_rev_hh_final])
        tax_revenue = tax_revenue.reset_index(drop=False)
        
        return tax_revenue
