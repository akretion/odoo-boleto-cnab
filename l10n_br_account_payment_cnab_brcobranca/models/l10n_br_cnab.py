# -*- coding: utf-8 -*-
# Copyright 2017 Akretion - Renato Lima <renato.lima@akretion.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import requests

from openerp import models, api


class L10nBrHrCnab(models.Model):
    _inherit = "l10n.br.cnab"

    @api.multi
    def processar_arquivo_retorno(self):
        import pudb; pudb.set_trace()
        #f = open(tempfile.mktemp(), 'w')
        #f.write(content)
        #f.close()
        
        files = {'data': base64.b64decode(self.arquivo_retorno)}
        res = requests.post(
            "http://172.16.98.2:9292/api/retorno",
            data={
                'type': 'cnab400',  # dict_brcobranca_cnab_type[order.mode.type.code],
                'bank': 'bradesco' # bank_name_brcobranca[0],
            }, files=files)




        arquivo_retono = base64.b64decode(self.arquivo_retorno)
        f = open('/tmp/cnab_retorno.ret', 'wb')
        f.write(arquivo_retono)
        f.close()
        arquivo_retono = codecs.open('/tmp/cnab_retorno.ret', encoding='ascii')
        arquivo_parser = Arquivo(bancodobrasil, arquivo=arquivo_retono)
        if not arquivo_parser.header.arquivo_codigo == u'2':
            raise exceptions.Warning(
                u"Este não é um arquivo de retorno!"
            )
        data_arquivo = str(arquivo_parser.header.arquivo_data_de_geracao)
        self.data_arquivo = fields.Date.from_string(
            data_arquivo[4:] + "-" + data_arquivo[2:4] + "-" +
            data_arquivo[0:2]
        )
        self.bank_account_id = self.env['res.partner.bank'].search(
            [('acc_number', '=', arquivo_parser.header.cedente_conta)]).id
        self.num_lotes = arquivo_parser.trailer.totais_quantidade_lotes
        self.num_eventos = arquivo_parser.trailer.totais_quantidade_registros
        for lote in arquivo_parser.lotes:
            account_bank_id_lote = self.env['res.partner.bank'].search(
                [('acc_number', '=', lote.header.cedente_conta)]
            ).id
            vals = {
                'account_bank_id': account_bank_id_lote,
                'empresa_inscricao_numero':
                    str(lote.header.empresa_inscricao_numero),
                'empresa_inscricao_tipo':
                    TIPO_INSCRICAO_EMPRESA[lote.header.empresa_inscricao_tipo],
                'servico_operacao':
                    TIPO_OPERACAO[lote.header.servico_operacao],
                'tipo_servico': TIPO_SERVICO[str(lote.header.servico_servico)],
                'mensagem': lote.header.mensagem1,
                'qtd_registros': lote.trailer.quantidade_registros,
                'total_valores': float(lote.trailer.somatoria_valores),
                'cnab_id': self.id,
            }
            lote_id = self.env['l10n.br.cnab.lote'].create(vals)
            for evento in lote.eventos:
                data_evento = str(
                    evento.credito_data_real)
                data_evento = fields.Date.from_string(
                    data_evento[4:] + "-" + data_evento[2:4] + "-" +
                    data_evento[0:2]
                )
                account_bank_id_lote = self.env['res.partner.bank'].search(
                    [
                        ('bra_number', '=', evento.favorecido_agencia),
                        ('bra_number_dig', '=', evento.favorecido_agencia_dv),
                        ('acc_number', '=', evento.favorecido_conta),
                        ('acc_number_dig', '=', evento.favorecido_conta_dv)
                    ])
                account_bank_id_lote = account_bank_id_lote.ids[0] \
                    if account_bank_id_lote else False
                favorecido_partner = self.env['res.partner.bank'].search(
                    [('owner_name', 'ilike', evento.favorecido_nome)]
                )
                favorecido_partner = favorecido_partner[0].partner_id.id \
                    if favorecido_partner else False
                bank_payment_line_id = self.env['bank.payment.line'].search(
                    [
                        ('name', '=', evento.credito_seu_numero)
                    ]
                )
                ocorrencias_dic = dict(CODIGO_OCORRENCIAS)
                ocorrencias = [
                    evento.ocorrencias[0:2],
                    evento.ocorrencias[2:4],
                    evento.ocorrencias[4:6],
                    evento.ocorrencias[6:8],
                    evento.ocorrencias[8:10]
                ]
                vals_evento = {
                    'data_real_pagamento': data_evento,
                    'segmento': evento.servico_segmento,
                    'favorecido_nome': favorecido_partner,
                    'favorecido_conta_bancaria': account_bank_id_lote,
                    'nosso_numero': str(evento.credito_nosso_numero),
                    'seu_numero': evento.credito_seu_numero,
                    'tipo_moeda': evento.credito_moeda_tipo,
                    'valor_pagamento': evento.credito_valor_pagamento,
                    'ocorrencias': evento.ocorrencias,
                    'str_motiv_a': ocorrencias_dic[ocorrencias[0]] if
                    ocorrencias[0] else '',
                    'str_motiv_b': ocorrencias_dic[ocorrencias[1]] if
                    ocorrencias[1] else '',
                    'str_motiv_c': ocorrencias_dic[ocorrencias[2]] if
                    ocorrencias[2] else '',
                    'str_motiv_d': ocorrencias_dic[ocorrencias[3]] if
                    ocorrencias[3] else '',
                    'str_motiv_e': ocorrencias_dic[ocorrencias[4]] if
                    ocorrencias[4] else '',
                    'lote_id': lote_id.id,
                    'bank_payment_line_id': bank_payment_line_id.id,
                }
                self.env['l10n.br.cnab.evento'].create(vals_evento)
                if evento.ocorrencias and bank_payment_line_id:
                    if '00' in ocorrencias:
                        bank_payment_line_id.write({'state2': 'paid'})
                    else:
                        bank_payment_line_id.write({'state2': 'exception'})

        return self.write({'state': 'done'})
