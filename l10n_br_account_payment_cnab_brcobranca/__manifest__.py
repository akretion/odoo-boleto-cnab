# -*- coding: utf-8 -*-
# Copyright 2017 Akretion
# @author Raphaël Valyi <raphael.valyi@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'L10n Br Account Payment CNAB Brcobranca',
    'description': """
        Imprime boletos usando a Gem brcobranca do Boletosimples""",
    'version': '10.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'Akretion',
    'website': 'www.akretion.com',
    'depends': [
        'l10n_br_account_banking_payment_cnab'
    ],
    'data': [
        'views/payment_mode.xml',
        'views/l10n_br_cnab_retorno_view.xml',
    ],
    'demo': [
    ],
    'test': [
        'tests/invoice_create.yml'
    ]
}
