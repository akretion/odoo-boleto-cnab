# -*- coding: utf-8 -*-
# Copyright 2017 Akretion
# @author Raphaël Valyi <raphael.valyi@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import time
from datetime import datetime

from openerp import models, api, workflow, fields, _
from openerp.addons.l10n_br_base.tools.misc import punctuation_rm

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

dict_brcobranca_bank = {
    '001': 'banco_brasil',
    '041': 'banrisul',
    '237': 'bradesco',
    '104': 'caixa',
    '399': 'hsbc',
    '341': 'itau',
    '033': 'santander',
    '748': 'sicredi',
    '004': 'banco_nordeste',
    '021': 'banestes',
    '756': 'sicoob',
}

dict_brcobranca_cnab_type = {
    '240': 'cnab240',
    '400': 'cnab400',
}


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

            if order.mode.bank_id.bank.bic in \
                    dict_brcobranca_bank:
                bank_name_brcobranca = dict_brcobranca_bank[
                                           order.mode.bank_id.bank.bic],
            else:
                raise UserError(
                    _('The Bank %s is not implemented in BRCobranca.')
                    % order.mode.bank_id.bank.name)

            if (bank_name_brcobranca[0] not in ('bradesco', 'itau')
                    or order.mode.type.code != '400'):
                raise UserError(
                    _('The Bank %s and CNAB %s are not implemented.')
                    % (order.mode.bank_id.bank.name,
                       order.mode.type.code))

            pagamentos = []
            for line in order.line_ids:

                linhas_pagamentos = {
                    'valor': line.amount_currency,
                    'data_vencimento': line.move_line_id.date_maturity,
                    'nosso_numero': line.move_line_id.boleto_own_number,
                    'documento_sacado': punctuation_rm(line.partner_id.cnpj_cpf),
                    'nome_sacado':
                        line.partner_id.legal_name.encode('utf-8').strip()[:40],
                    'numero': str(line.move_line_id.name.encode('utf-8'))[:10],
                    'endereco_sacado': str(
                       line.partner_id.street.encode('utf-8') + ', ' + str(
                           line.partner_id.number.encode('utf-8')))[:40],
                    'bairro_sacado':
                           line.partner_id.district.encode('utf-8').strip(),
                    'cep_sacado': punctuation_rm(line.partner_id.zip),
                    'cidade_sacado':
                        line.partner_id.l10n_br_city_id.name.encode('utf-8'),
                    'uf_sacado': line.partner_id.state_id.code,
                    'identificacao_ocorrencia': order.codigo_instrucao_movimento
                }
                if line.move_line_id.payment_mode_id.boleto_perc_mora:
                    linhas_pagamentos['codigo_multa'] = '2'
                    linhas_pagamentos['percentual_multa'] =\
                        line.move_line_id.payment_mode_id.boleto_perc_mora
                precision = self.env['decimal.precision']
                precision_account = precision.precision_get('Account')
                if line.move_line_id.payment_mode_id.cnab_percent_interest:
                    linhas_pagamentos['valor_mora'] = round(
                        line.move_line_id.debit *
                        ((line.move_line_id.payment_mode_id.cnab_percent_interest / 100)
                         / 30), precision_account)
                if line.move_line_id.payment_term_id.discount_perc:
                    linhas_pagamentos['data_desconto'] = datetime.strptime(
                        line.move_line_id.date_maturity,
                          '%Y-%m-%d').strftime('%Y/%m/%d')
                    linhas_pagamentos['valor_desconto'] = round(
                        line.move_line_id.debit * (
                            line.move_line_id.payment_term_id.discount_perc / 100),
                        precision_account)

                pagamentos.append(linhas_pagamentos)

            remessa_values = {
                'carteira': str(order.mode.boleto_carteira),
                'agencia': int(order.mode.bank_id.bra_number),
                # 'digito_agencia': order.mode.bank_id.bra_number_dig,
                'conta_corrente': int(punctuation_rm(order.mode.bank_id.acc_number)),
                'digito_conta': order.mode.bank_id.acc_number_dig[0],
                'empresa_mae':
                  order.mode.bank_id.partner_id.legal_name[:30].encode('utf-8'),
                'documento_cedente': punctuation_rm(
                    order.mode.bank_id.partner_id.cnpj_cpf),
                'pagamentos': pagamentos,
                'sequencial_remessa': self.env['ir.sequence'].next_by_id(
                    order.mode.cnab_sequence_id.id)
            }

            if (bank_name_brcobranca[0] == 'bradesco'
                    and order.mode.type.code == '400'):
                remessa_values[
                    'codigo_empresa'] = int(order.mode.codigo_convenio)

            content = json.dumps(remessa_values)
            f = open(tempfile.mktemp(), 'w')
            f.write(content)
            f.close()
            files = {'data': open(f.name, 'rb')}
            res = requests.post(
                "http://boleto_cnab_api:9292/api/remessa",
                data={
                    'type': dict_brcobranca_cnab_type[order.mode.type.code],
                    'bank': bank_name_brcobranca[0],
                }, files=files)
            # print "AAAAAAAA", res.status_code, str(res.status_code)[0]
            # print 'RES.CONTENT', res.content
            if res.content[0] == '0':
                remessa = res.content
            else:
                raise UserError(res.text)

            self.state = 'done'
            self.cnab_file = base64.b64encode(remessa)

            # Criando instancia do CNAB a partir do código do banco
#            cnab = Cnab.get_cnab(
#                order.mode.bank_id.bank_bic, order.mode.type.code)()

#                remessa = cnab.remessa(order)

            if order.mode.type.code == '240':
                self.name = 'CB%s%s.REM' % (
                    time.strftime('%d%m'), str(order.file_number))
            elif order.mode.type.code == '400':
                self.name = 'CB%s%02d.REM' % (
                    time.strftime('%d%m'), order.file_number or 1)
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
