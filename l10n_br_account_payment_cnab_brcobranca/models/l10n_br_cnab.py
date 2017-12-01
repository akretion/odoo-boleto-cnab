# -*- coding: utf-8 -*-
# Copyright 2017 Akretion - Renato Lima <renato.lima@akretion.com.br>
# Copyright 2017 Akretion - Magno Costa <magno.costa@akretion.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import requests
import json
import datetime

from openerp import models, fields, api, _
from openerp.exceptions import Warning as UserError

DICT_OCORRENCIAS_BRADESCO = {
    '02': u'Entrada Confirmada (verificar motivo na posição 319 a 328)',
    '03': u'Entrada Rejeitada ( verificar motivo na posição 319 a 328)',
    '06': u'Liquidação normal (sem motivo)',
    '09': u'Baixado Automat. via Arquivo (verificar motivo posição 319 a 328)',
    '10': u'Baixado conforme instruções da Agência('
          u'verificar motivo pos.319 a 328)',
    '11': u'Em Ser - Arquivo de Títulos pendentes (sem motivo)',
    '12': u'Abatimento Concedido (sem motivo)',
    '13': u'Abatimento Cancelado (sem motivo)',
    '14': u'Vencimento Alterado (sem motivo)',
    '15': u'Liquidação em Cartório (sem motivo)',
    '16': u'Título Pago em Cheque – Vinculado',
    '17': u'Liquidação após baixa ou Título não registrado (sem motivo)',
    '18': u'Acerto de Depositária (sem motivo)',
    '19': u'Confirmação Receb. Inst. de Protesto '
          u'(verificar motivo pos.295 a 295)',
    '20': u'Confirmação Recebimento Instrução Sustação de'
          u' Protesto (sem motivo)',
    '21': u'Acerto do Controle do Participante (sem motivo)',
    '22': u'Título Com Pagamento Cancelado',
    '23': u'Entrada do Título em Cartório (sem motivo)',
    '24': u'Entrada rejeitada por CEP Irregular'
          u' (verificar motivo pos.319 a 328)',
    '25': u'Confirmação Receb.Inst.de Protesto Falimentar'
          u' (verificar pos.295 a 295)',
    '27': u'Baixa Rejeitada (verificar motivo posição 319 a 328)',
    '28': u'Débito de tarifas/custas (verificar motivo na posição 319 a 328)',
    '29': u'Ocorrências do Pagador (NOVO)',
    '30': u'Alteração de Outros Dados Rejeitados '
          u'(verificar motivo pos.319 a 328)',
    '32': u'Instrução Rejeitada (verificar motivo posição 319 a 328)',
    '33': u'Confirmação Pedido Alteração Outros Dados (sem motivo)',
    '34': u'Retirado de Cartório e Manutenção Carteira (sem motivo)',
    '35': u'Desagendamento do débito automático '
          u'(verificar motivos pos. 319 a 328)',
    '40': u'Estorno de pagamento (NOVO)',
    '55': u'Sustado judicial (NOVO)',
    '68': u'Acerto dos dados do rateio de Crédito (verificar motivo posição de'
          u' status do registro tipo 3)',
    '69': u'Cancelamento dos dados do rateio (verificar motivo posição de'
          u' status do registro tipo 3)',
    '073': u'Confirmação Receb. Pedido de Negativação (NOVO)',
    '074': u'Confir Pedido de Excl de Negat (com ou sem baixa) (NOVO)',
    '00': u'Nota: Para as ocorrências sem motivos, as posições serão'
          u' informadas com Zeros.',
}


class L10nBrHrCnab(models.Model):
    _inherit = "l10n.br.cnab"

    account_journal = fields.Many2one(
        'account.journal', 'Journal used in Bank Statement',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help='Journal used in create of Bank Statement.'
    )
    cnab_type = fields.Selection(
        [('cnab400', u'CNAB 400')], 'CNAB Type File',
        default='cnab400',
        readonly=True,
        states={'draft': [('readonly', False)]}
    )
    bank = fields.Selection(
        [('bradesco', u'Bradesco')], 'Bank',
        default='bradesco',
        readonly=True,
        states={'draft': [('readonly', False)]}
    )

    @api.multi
    def processar_arquivo_retorno(self):

        files = {'data': base64.b64decode(self.arquivo_retorno)}
        res = requests.post(
            "http://boleto_cnab_api:9292/api/retorno",
            data={
                'type': self.cnab_type,
                'bank': self.bank,
            }, files=files)

        if res.status_code != 201:
            raise UserError(res.text)

        string_result = res.json()
        data = json.loads(string_result)

        if self.cnab_type == 'cnab400' and self.bank == 'bradesco':
            self.processar_arquivo_retorno_cnab400_bradesco(data)

    @api.multi
    def processar_arquivo_retorno_cnab400_bradesco(self, data):

        lote_id = self.env['l10n.br.cnab.lote'].create({'cnab_id': self.id})

        quantidade_registros = 0
        total_valores = 0
        balance_end_real = 0.0
        line_statement_vals = []

        for dict_line in data:
            if int(dict_line['codigo_registro']) != 1:
                # Existe o codigo de registro 9 que eh um totalizador
                # porem os campos estao colocados em outras posicoes
                # que nao estao mapeadas no BRCobranca
                continue

            quantidade_registros += 1
            obj_account_move_line = self.env['account.move.line'].search(
                [('boleto_own_number', '=', dict_line['nosso_numero'][:11])]
            )

            valor_titulo = float(
                str(dict_line['valor_titulo'][0:11] + '.' +
                    dict_line['valor_titulo'][11:]))

            valor_recebido = 0.0
            if dict_line['valor_recebido']:
                valor_recebido = float(
                    str(dict_line['valor_recebido'][0:11] + '.' +
                        dict_line['valor_recebido'][11:]))
            total_valores += valor_titulo

            if (dict_line['data_ocorrencia'] == '000000' or
                    not dict_line['data_ocorrencia']):
                data_ocorrencia = dict_line['data_de_ocorrencia']
            else:
                data_ocorrencia = datetime.datetime.strptime(
                    str(dict_line['data_ocorrencia']), "%d%m%y").date()

            if not obj_account_move_line:
                vals_evento = {
                   'lote_id': lote_id.id,
                   'ocorrencias': DICT_OCORRENCIAS_BRADESCO[
                       dict_line['codigo_ocorrencia']],
                   'data_ocorrencia': data_ocorrencia,
                   'str_motiv_a':
                       u' * - BOLETO NÃO ENCONTRADO DENTRO DO PROGRAMA',
                   'nosso_numero': dict_line['nosso_numero'],
                   'seu_numero': dict_line['documento_numero'],
                   'valor_pagamento': valor_titulo,
                }
                self.env['l10n.br.cnab.evento'].create(vals_evento)
                continue

            if (dict_line['data_credito'] == '000000' or
                    not dict_line['data_credito']):
                data_credito = dict_line['data_credito']
            else:
                data_credito = datetime.datetime.strptime(
                    str(dict_line['data_credito']), "%d%m%y").date()

            if dict_line['codigo_ocorrencia'] in ('06', '17'):
                vals_evento = {
                    'lote_id': lote_id.id,
                    'data_ocorrencia': data_ocorrencia,
                    'data_real_pagamento': data_credito.strftime("%Y-%m-%d"),
                    # 'segmento': evento.servico_segmento,
                    #'favorecido_nome':
                    #    obj_account_move_line.company_id.partner_id.name,
                    'favorecido_conta_bancaria':
                        obj_account_move_line.payment_mode_id.bank_id.id,
                    'nosso_numero': dict_line['nosso_numero'],
                    'seu_numero': dict_line['documento_numero'] or
                        obj_account_move_line.name,
                    # 'tipo_moeda': evento.credito_moeda_tipo,
                    'valor_pagamento': valor_recebido,
                    'ocorrencias': DICT_OCORRENCIAS_BRADESCO[
                        dict_line['codigo_ocorrencia']].encode('utf-8'),
                    # 'str_motiv_a': ocorrencias_dic[ocorrencias[0]] if
                    # ocorrencias[0] else '',
                    # 'str_motiv_b': ocorrencias_dic[ocorrencias[1]] if
                    # ocorrencias[1] else '',
                    # 'str_motiv_c': ocorrencias_dic[ocorrencias[2]] if
                    # ocorrencias[2] else '',
                    # 'str_motiv_d': ocorrencias_dic[ocorrencias[3]] if
                    # ocorrencias[3] else '',
                    # 'str_motiv_e': ocorrencias_dic[ocorrencias[4]] if
                    # ocorrencias[4] else '',
                    # 'lote_id': lote_id.id,
                    # 'bank_payment_line_id': bank_payment_line_id.id,
                }

                # Monta o dicionario que sera usado
                # para criar o Extrato Bancario
                balance_end_real += valor_recebido
                line_statement_vals.append({
                    'name': obj_account_move_line.name or '?',
                    'amount': valor_recebido,
                    'partner_id': obj_account_move_line.partner_id.id,
                    'ref': obj_account_move_line.ref,
                    'date': obj_account_move_line.date,
                    'amount_currency': valor_recebido,
                    'currency_id': obj_account_move_line.currency_id.id,
                })

            else:
                vals_evento = {
                    'lote_id': lote_id.id,
                    'ocorrencias': DICT_OCORRENCIAS_BRADESCO[
                        dict_line['codigo_ocorrencia']].encode('utf-8'),
                    'data_ocorrencia': data_ocorrencia,
                    'nosso_numero': dict_line['nosso_numero'],
                    'seu_numero': obj_account_move_line.name,
                    'valor_pagamento': valor_titulo,
                }

            self.env['l10n.br.cnab.evento'].create(vals_evento)

        lote_id.total_valores = total_valores
        lote_id.qtd_registros = quantidade_registros
        self.num_lotes = 1
        self.num_eventos = quantidade_registros

        # FIXME - Encontrar uma forma melhor de localizar a conta bancaria
        lote_id.account_bank_id =\
            obj_account_move_line.payment_mode_id.bank_id

        # Criacao de um Extrato Bancario para ser conciliado
        # pelo usuario permitindo assim o tratamento de valores
        # a mais ou a menos pelo operador
        if line_statement_vals:
            vals_bank_statement = {
                'journal_id': self.account_journal.id,
                'balance_end_real': balance_end_real,
            }
            statement = self.env[
                'account.bank.statement'].create(vals_bank_statement)
            statement_line_obj = self.env['account.bank.statement.line']
            for line in line_statement_vals:
                line['statement_id'] = statement.id
                statement_line_obj.create(line)

        return self.write({'state': 'done'})


class L10nBrHrCnabEvento(models.Model):
    _inherit = "l10n.br.cnab.evento"

    data_ocorrencia = fields.Date(string=u"Data da Ocorrência")
