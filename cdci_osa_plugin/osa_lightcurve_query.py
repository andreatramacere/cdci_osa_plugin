"""
Overview
--------

general info about this module


Classes and Inheritance Structure
----------------------------------------------
.. inheritance-diagram::

Summary
---------
.. autosummary::
   list of the module you want

Module API
----------
"""

from __future__ import absolute_import, division, print_function

from builtins import (bytes, str, open, super, range,
                      zip, round, input, int, pow, object, map, zip)

__author__ = "Andrea Tramacere"

# Standard library
# eg copy
# absolute import rg:from copy import deepcopy
import os

# Dependencies
# eg numpy
# absolute import eg: import numpy as np

# Project
# relative import eg: from .mod import f


import ddosaclient as dc

# Project
# relative import eg: from .mod import f
import  numpy as np
from pathlib import Path

from astropy.io import fits as pf
from cdci_data_analysis.analysis.io_helper import FitsFile
from cdci_data_analysis.analysis.queries import LightCurveQuery
from cdci_data_analysis.analysis.products import LightCurveProduct,QueryProductList,QueryOutput
from cdci_data_analysis.analysis.io_helper import FilePath
from cdci_data_analysis.analysis.plot_tools import ScatterPlot

from .osa_dataserve_dispatcher import OsaDispatcher



class IsgriLigthtCurve(LightCurveProduct):
    def __init__(self,name,file_name,data,header,prod_prefix=None,out_dir=None,src_name=None):


        super(IsgriLigthtCurve, self).__init__(name,
                                               data,
                                               header,
                                               file_name=file_name,
                                               name_prefix=prod_prefix,
                                               file_dir=out_dir,
                                               src_name=src_name)



    # @classmethod
    # def build_from_ddosa_res_old(cls,
    #                          name,
    #                          file_name,
    #                          res,
    #                          src_name='ciccio',
    #                          prod_prefix = None,
    #                          out_dir = None):
    #
    #     #hdu_list = pf.open(res.lightcurve)
    #     hdu_list = FitsFile(res.lightcurve).open()
    #     data = None
    #     header=None
    #
    #     for hdu in hdu_list:
    #         if hdu.name == 'ISGR-SRC.-LCR':
    #             print('name', hdu.header['NAME'])
    #             if hdu.header['NAME'] == src_name:
    #                 data = hdu.data
    #                 header = hdu.header
    #
    #         lc = cls(name=name, data=data, header=header,file_name=file_name,out_dir=out_dir,prod_prefix=prod_prefix,src_name=src_name)
    #
    #     return lc

    @classmethod
    def build_from_ddosa_res(cls,
                             res,
                             src_name='',
                             prod_prefix='',
                             out_dir=None):



        lc_list = []

        if out_dir is None:
            out_dir = './'

        if prod_prefix is None:
            prod_prefix=''

        for source_name, lightcurve_attr in res.extracted_sources:
            lc_paht = getattr(res, lightcurve_attr)
            print('lc file-->', lc_paht, lightcurve_attr)

            data = None
            header = None

            hdu_list = FitsFile(lc_paht).open()
            for hdu in hdu_list:
                if hdu.name == 'ISGR-SRC.-LCR':
                    # print('name', hdu.header['NAME'])
                    name = hdu.header['NAME']
                    data = hdu.data
                    header = hdu.header

            file_name = prod_prefix + '_' + Path(lc_paht).resolve().stem

            lc = cls(name=name, data=data, header=header, file_name=file_name, out_dir=out_dir, prod_prefix=prod_prefix,
                     src_name=name)

            lc_list.append(lc)

        return lc_list

    def get_html_draw(self, plot=False):
        # from astropy.io import fits as pf
        # print ('loading -->',self.file_path.path)

        # hdul = pf.open(self.file_path.path)
        hdul = FitsFile(self.file_path.path).open()

        data = hdul[1].data
        header = hdul[1].header

        import matplotlib
        # matplotlib.use('TkAgg')
        #import pylab as plt
        #fig, ax = plt.subplots()

        #filtering zero flux values
        msk_non_zero = np.count_nonzero([data['RATE'], data['ERROR']], axis=0) > 0
        data=data[msk_non_zero]

        x = data['TIME']
        y = data['RATE']
        dy = data['ERROR']
        mjdref = header['mjdref'] + np.int(x.min())



        x = x - np.int(x.min())

        sp=ScatterPlot(w=600,h=600,x_label='MJD-%d  (days)' % mjdref,y_label='Rate  (cts/s)')
        sp.add_errorbar(x,y,yerr=dy)
        footer_str=''
        try:
            slope = None
            normalized_slope = None
            chisq_red = None
            poly_deg = 0
            p, chisq, chisq_red, dof,xf,yf = self.do_linear_fit(x, y, dy, poly_deg, 'constant fit')
            sp.add_line(xf,yf,'constant fit',color='green')

            exposure = header['TIMEDEL'] * data['FRACEXP'].sum()
            exposure *= 86400.
            footer_str = 'Exposure %5.5f (s) \n' % exposure
            if p is not None:
                footer_str += '\n'
                footer_str += 'Constant fit\n'
                footer_str += 'flux level %5.5f (cts/s)\n' % p[0]
                footer_str += 'dof ' + '%d' % dof + '\n'
                footer_str += 'Chi-squared red. %5.5f\n' % chisq_red

        except:
            pass

        try:
            poly_deg = 1
            p, chisq, chisq_red, dof,xf,yf = self.do_linear_fit(x, y, dy, poly_deg, 'linear fit')
            if p is not None:
                footer_str += '\n'
                footer_str += 'Linear fit\n'
                footer_str += 'slope %5.5f\n' % p[0]
                footer_str += 'dof ' + '%d' % dof + '\n'
                footer_str += 'Chi-squared red. %5.5f\n' % chisq_red

            sp.add_line(xf, yf, 'linear fit',color='orange')
        except:
            pass



        html_dict= sp.get_html_draw()


        res_dict = {}
        res_dict['image'] =html_dict
        res_dict['header_text'] = ''
        res_dict['table_text'] = ''
        res_dict['footer_text'] = footer_str


        return res_dict

    def do_linear_fit(self, x, y, dy, poly_deg, label):

        p = None
        chisq = None
        chisq_red = None
        dof = None
        x_grid = None
        y_grid=None

        if y.size > poly_deg + 1:
            p = np.polyfit(x, y, poly_deg)

            x_grid = np.linspace(x.min(), x.max(), 100)
            lin_fit = np.poly1d(p)

            chisq = (lin_fit(x) - y) ** 2 / dy ** 2
            dof = y.size - (poly_deg + 1)
            chisq_red = chisq.sum() / float(dof)
            #plt.plot(x_grid, lin_fit(x_grid), '--', label=label)
            y_grid=lin_fit(x_grid)

        return p, chisq, chisq_red, dof,x_grid, y_grid




class OsaLightCurveQuery(LightCurveQuery):

    def __init__(self, name):

        super(OsaLightCurveQuery, self).__init__(name)



    def get_data_server_query(self, instrument,
                              config=None):

        scwlist_assumption, cat, extramodules, inject=OsaDispatcher.get_osa_query_base(instrument)
        E1=instrument.get_par_by_name('E1_keV').value
        E2=instrument.get_par_by_name('E2_keV').value
        src_name = instrument.get_par_by_name('src_name').value
        delta_t = instrument.get_par_by_name('time_bin')._astropy_time_delta.sec
        target, modules, assume=self.set_instr_dictionaries(extramodules,scwlist_assumption,E1,E2,src_name,delta_t)



        q = OsaDispatcher(config=config,instrument=instrument, target=target, modules=modules, assume=assume, inject=inject)

        return q


    def set_instr_dictionaries(self, extramodules,scwlist_assumption,E1,E2,src_name,delta_t):
        raise RuntimeError('Must be specified for each instrument')


    def process_product_method(self, instrument, prod_list):

        _names = []
        _lc_path = []
        _html_fig = []
        _data_list=[]
        for query_lc in prod_list.prod_list:
            print('name',query_lc.name)
            query_lc.write()
            _names.append(query_lc.name)
            _lc_path.append(str(query_lc.file_path.name))
            _html_fig.append(query_lc.get_html_draw())
            # print(_html_fig[-1])
            _data = {}
            _data['name'] = query_lc.name
            _data['mjdref'] = query_lc.header['mjdref']
            _data['time'] = query_lc.data['TIME'].tolist()
            _data['time_units'] = 'mjd'

            _data['time_del'] = query_lc.header['TIMEDEL']
            _data['rate'] = query_lc.data['RATE'].tolist()
            _data['rate_err'] = query_lc.data['ERROR'].tolist()


            _data_list.append(_data)






        query_out = QueryOutput()

        query_out.prod_dictionary['data'] = _data_list
        query_out.prod_dictionary['name'] = _names
        query_out.prod_dictionary['file_name'] = _lc_path
        query_out.prod_dictionary['image'] =_html_fig
        query_out.prod_dictionary['download_file_name'] = 'light_curves.tar.gz'
        query_out.prod_dictionary['prod_process_message'] = ''

        return query_out

class IsgriLightCurveQuery(OsaLightCurveQuery):
    def __init__(self,name ):
        super(IsgriLightCurveQuery, self).__init__(name)





    def build_product_list(self,instrument,res,out_dir,prod_prefix=None):

        src_name = instrument.get_par_by_name('src_name').value

        prod_list = IsgriLigthtCurve.build_from_ddosa_res(res,
                                                          src_name=src_name,
                                                          prod_prefix=prod_prefix,
                                                          out_dir=out_dir)

        # print('spectrum_list',spectrum_list)

        return prod_list

    def set_instr_dictionaries(self, extramodules, scwlist_assumption, E1, E2, src_name, delta_t):
        print('-->lc standard mode from scw_list', scwlist_assumption)
        print('-->src_name', src_name)
        target = "ISGRILCSum"

        if extramodules is None:
            extramodules = []

        modules = ["git://ddosa"] + extramodules + ['git://process_isgri_lc', 'git://ddosa_delegate']

        assume = ['process_isgri_lc.ScWLCList(input_scwlist=%s)' % scwlist_assumption[0],
                  scwlist_assumption[1],
                  'ddosa.ImageBins(use_ebins=[(%(E1)s,%(E2)s)],use_version="onebin_%(E1)s_%(E2)s")' % dict(E1=E1,
                                                                                                           E2=E2),
                  'ddosa.LCEnergyBins(use_ebins=[(%(E1)s,%(E2)s)],use_version="onebin_%(E1)s_%(E2)s")' % dict(E1=E1,
                                                                                                              E2=E2),
                  'ddosa.ImagingConfig(use_SouFit=0,use_version="soufit0_p2",use_DoPart2=1)',
                  'ddosa.CatForLC(use_minsig=3)',
                  'ddosa.LCTimeBin(use_time_bin_seconds=%f)' % delta_t]

        return target, modules, assume

    def get_dummy_products(self, instrument, config, out_dir='./'):
        src_name = instrument.get_par_by_name('src_name').value

        dummy_cache = config.dummy_cache
        delta_t = instrument.get_par_by_name('time_bin')._astropy_time_delta.sec
        print('delta_t is sec', delta_t)
        query_lc = IsgriLigthtCurve.from_fits_file(inf_file='%s/query_lc.fits' % dummy_cache,
                                                    out_file_name='query_lc.fits',
                                                    prod_name='isgri_lc',
                                                    ext=1,
                                                    out_dir=out_dir)
        print('name', query_lc.header['NAME'])
        query_lc.name=query_lc.header['NAME']
        #if src_name is not None:
        #    if query_lc.header['NAME'] != src_name:
        #        query_lc.data = None

        prod_list = QueryProductList(prod_list=[query_lc])

        return prod_list


