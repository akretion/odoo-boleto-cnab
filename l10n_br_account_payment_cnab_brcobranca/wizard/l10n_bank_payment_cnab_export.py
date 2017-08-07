# coding: utf-8

import base64
import time

from openerp import models, api, workflow, fields, _
from openerp.exceptions import Warning as UserError

import logging


import requests
import json
import tempfile
from openerp.exceptions import Warning as UserError


_logger = logging.getLogger(__name__)
try:
    from cnab240.errors import (Cnab240Error)
except ImportError as err:
    _logger.debug = err


class L10nPaymentCnab(models.TransientModel):
    _inherit = 'payment.cnab'

    @api.multi
    def export(self):
        for order_id in self.env.context.get('active_ids', []):

            order = self.env['payment.order'].browse(order_id)
            if not order.line_ids:
                raise UserError(
                    _('Error'),
                    _('Adicione pelo menos uma linha na ordem de pagamento.'))

            # see remessa fields here:
            # https://github.com/kivanio/brcobranca/blob/master/lib/brcobranca/remessa/base.rb
            # https://github.com/kivanio/brcobranca/tree/master/lib/brcobranca/remessa/cnab240
            # https://github.com/kivanio/brcobranca/tree/master/lib/brcobranca/remessa/cnab400
            # and a test here:
            # https://github.com/kivanio/brcobranca/blob/master/spec/brcobranca/remessa/cnab400/itau_spec.rb

            pagamentos = [{
                      'valor': 199.9,
               #'data_vencimento': Date.current,
               'nosso_numero': 123,
               'documento_sacado': '12345678901',
               'nome_sacado': 'PABLO DIEGO JOSÉ FRANCISCO DE PAULA JUAN NEPOMUCENO MARÍA DE LOS REMEDIOS CIPRIANO DE LA SANTÍSSIMA TRINIDAD RUIZ Y PICASSO',
               'endereco_sacado': 'RUA RIO GRANDE DO SUL São paulo Minas caçapa da silva junior',
               'bairro_sacado': 'São josé dos quatro apostolos magros',
               'cep_sacado': '12345678',
               'cidade_sacado': 'Santa rita de cássia maria da silva',
               'uf_sacado': 'SP'
            }]

            remessa_values = {
              'carteira': '123',
              'agencia': '1234',
              'conta_corrente': '12345',
              'digito_conta': '1',
              'empresa_mae': 'SOCIEDADE BRASILEIRA DE ZOOLOGIA LTDA',
              'documento_cedente': '12345678910',
              'pagamentos': pagamentos
            }

            content = json.dumps(remessa_values)
            print content
            f = open(tempfile.mktemp(), 'w')
            f.write(content)
            f.close()
            files = {'data': open(f.name, 'rb')}
            res = requests.post("http://boleto_api:9292/api/remessa",
                                data={'type': 'cnab400', 'bank':'itau'},
                                files=files)
            print "AAAAAAAA", res.status_code
            if str(res.status_code)[0] == '2':
               remessa= res.content
            else:
               raise UserError(res.text)

            print remessa
            self.state = 'done'
            self.cnab_file = base64.b64encode(remessa)

            # Criando instancia do CNAB a partir do código do banco
#            cnab = Cnab.get_cnab(
#                order.mode.bank_id.bank_bic, order.mode.type.code)()

#                remessa = cnab.remessa(order)

            if order.mode.type.code == '240':
                self.name = 'CB%s%s.REM' % (
                    time.strftime('%d%m'), str(order.file_number))
            # elif order.mode.type.code == '400':
            #     self.name = 'CB%s%s.REM' % (
            #         time.strftime('%d%m'), str(suf_arquivo))
            elif order.mode.type.code == '500':
                self.name = 'PG%s%s.REM' % (
                    time.strftime('%d%m'), str(order.file_number))
            self.state = 'done'
            self.cnab_file = base64.b64encode(remessa)
            order.cnab_file = base64.b64encode(remessa)
            order.cnab_filename = self.name

            workflow.trg_validate(
                self.env.uid, 'payment.order', order_id, 'done', self.env.cr)

            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': self.id,
                'target': 'new',
            }

    @api.multi
    def done(self):
        return {'type': 'ir.actions.act_window_close'}
