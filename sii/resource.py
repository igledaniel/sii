# coding=utf-8
from sii import __SII_VERSION__
from sii.models import invoices_record

SIGN = {'B': -1, 'A': -1, 'N': 1, 'R': 1}


def get_importe_no_sujeto_a_iva(invoice):
    importe_no_sujeto = 0

    for line in invoice.invoice_line:
        no_iva = True
        for tax in line.invoice_line_tax_id:
            if 'iva' in tax.name.lower():
                no_iva = False
                break
        if no_iva:
            importe_no_sujeto += line.price_subtotal

    return importe_no_sujeto


def get_iva_values(invoice, in_invoice):
    vals = {
        'sujeta_a_iva': False,
        'detalle_iva': [],
        'no_sujeta_a_iva': False
    }
    for tax in invoice.tax_line:
        if 'iva' in tax.name.lower():
            iva = {
                'BaseImponible': SIGN[invoice.rectificative_type] * tax.base,
                'TipoImpositivo': tax.tax_id.amount * 100
            }
            if in_invoice:
                iva.update({
                    'CuotaRepercutida':
                        SIGN[invoice.rectificative_type] * tax.tax_amount
                })
            else:
                iva.update({
                    'CuotaSoportada':
                        SIGN[invoice.rectificative_type] * tax.tax_amount
                })
            vals['sujeta_a_iva'] = True
            vals['detalle_iva'].append(iva)
        else:
            vals['no_sujeta_a_iva'] = True
    return vals


def get_factura_emitida(invoice):
    iva_values = get_iva_values(invoice, in_invoice=True)
    desglose_factura = {}

    if iva_values['sujeta_a_iva']:
        desglose_factura['Sujeta'] = {
            'NoExenta': {  # TODO Exenta o no exenta??
                'TipoNoExenta': 'S1',
                'DesgloseIVA': {
                    'DetalleIVA': iva_values['detalle_iva']
                }
            }
        }
    if iva_values['no_sujeta_a_iva']:
        importe_no_sujeto = get_importe_no_sujeto_a_iva(invoice)
        if 'islas canarias' not in invoice.fiscal_position.name.lower():
            desglose_factura['NoSujeta'] = {
                'ImportePorArticulos7_14_Otros': importe_no_sujeto
            }
        else:
            desglose_factura['NoSujeta'] = {
                'ImporteTAIReglasLocalizacion': importe_no_sujeto
            }

    factura_expedida = {
        'TipoFactura': 'F1',  # TODO change to rectificativa
        'ClaveRegimenEspecialOTrascendencia':
            invoice.fiscal_position.sii_out_clave_regimen_especial,
        'ImporteTotal': SIGN[invoice.rectificative_type] * invoice.amount_total,
        'DescripcionOperacion': invoice.name,
        'Contraparte': {
            'NombreRazon': invoice.partner_id.name,
            'NIF': invoice.partner_id.vat
        },
        'TipoDesglose': {
            'DesgloseFactura': desglose_factura
        }
    }

    return factura_expedida


def get_factura_recibida(invoice):
    iva_values = get_iva_values(invoice, in_invoice=False)
    cuota_deducible = 0

    if iva_values['sujeta_a_iva']:
        desglose_factura = {  # TODO to change
            # 'InversionSujetoPasivo': {
            #     'DetalleIVA': iva_values['detalle_iva']
            # },
            'DesgloseIVA': {
                'DetalleIVA': iva_values['detalle_iva']
            }
        }

        for detalle_iva in iva_values['detalle_iva']:
            cuota_deducible += detalle_iva['CuotaSoportada']
    else:
        desglose_factura = {
            'DesgloseIVA': {
                'DetalleIVA': {
                    'BaseImponible': 0  # TODO deixem de moment 0 perquè no tindrem inversio sujeto pasivo
                }
            }
        }

    factura_recibida = {
        'TipoFactura': 'F1',  # TODO change to rectificativa
        'ClaveRegimenEspecialOTrascendencia':
            invoice.fiscal_position.sii_in_clave_regimen_especial,
        'ImporteTotal': SIGN[invoice.rectificative_type] * invoice.amount_total,
        'DescripcionOperacion': invoice.name,
        'Contraparte': {
            'NombreRazon': invoice.partner_id.name,
            'NIF': invoice.partner_id.vat
        },
        'DesgloseFactura': desglose_factura,
        'CuotaDeducible': cuota_deducible,
        'FechaRegContable': '2017-12-31'  # TODO to change
    }

    return factura_recibida


def get_header(invoice):
    cabecera = {
        'IDVersionSii': __SII_VERSION__,
        'Titular': {
            'NombreRazon': invoice.company_id.partner_id.name,
            'NIF': invoice.company_id.partner_id.vat
        },
        'TipoComunicacion': 'A0' if not invoice.sii_sent else 'A1'
    }

    return cabecera


def get_factura_rectificativa_fields():
    rectificativa_fields = {
        'TipoRectificativa': 'S',  # Por sustitución
        'ImporteRectificacion': {
            'BaseRectificada': 0,
            'CuotaRectificada': 0
        }
    }

    return rectificativa_fields


def get_factura_emitida_dict(invoice, rectificativa=False):
    obj = {
        'SuministroLRFacturasEmitidas': {
            'Cabecera': get_header(invoice),
            'RegistroLRFacturasEmitidas': {
                'PeriodoImpositivo': {
                    'Ejercicio': invoice.period_id.name[3:7],
                    'Periodo': invoice.period_id.name[0:2]
                },
                'IDFactura': {
                    'IDEmisorFactura': {
                        'NIF': invoice.company_id.partner_id.vat
                    },
                    'NumSerieFacturaEmisor': invoice.number,
                    'FechaExpedicionFacturaEmisor': invoice.date_invoice
                },
                'FacturaExpedida': get_factura_emitida(invoice)
            }
        }
    }

    if rectificativa:
        vals = get_factura_rectificativa_fields()

        (
            obj['SuministroLRFacturasEmitidas']['RegistroLRFacturasEmitidas']
            ['FacturaExpedida']
        ).update(vals)

    return obj


def get_factura_recibida_dict(invoice, rectificativa=False):
    obj = {
        'SuministroLRFacturasRecibidas': {
            'Cabecera': get_header(invoice),
            'RegistroLRFacturasRecibidas': {
                'PeriodoImpositivo': {
                    'Ejercicio': invoice.period_id.name[3:7],
                    'Periodo': invoice.period_id.name[0:2]
                },
                'IDFactura': {
                    'IDEmisorFactura': {
                        'NIF': invoice.partner_id.vat
                    },
                    'NumSerieFacturaEmisor': invoice.number,
                    'FechaExpedicionFacturaEmisor': invoice.date_invoice
                },
                'FacturaRecibida': get_factura_recibida(invoice)
            }
        }
    }

    if rectificativa:
        vals = get_factura_rectificativa_fields()

        (
            obj['SuministroLRFacturasRecibidas']['RegistroLRFacturasRecibidas']
            ['FacturaRecibida']
        ).update(vals)

    return obj


class SII(object):
    @staticmethod
    def generate_object(invoice):

        if invoice.type == 'in_invoice':
            invoice_model = invoices_record.SuministroFacturasRecibidas()
            invoice_dict = get_factura_recibida_dict(invoice)
        elif invoice.type == 'out_invoice':
            invoice_model = invoices_record.SuministroFacturasEmitidas()
            invoice_dict = get_factura_emitida_dict(invoice)
        elif invoice.type == 'in_refund':
            invoice_model = invoices_record.SuministroFacturasRecibidas()
            invoice_dict = get_factura_recibida_dict(invoice, rectificativa=True)
        elif invoice.type == 'out_refund':
            invoice_model = invoices_record.SuministroFacturasEmitidas()
            invoice_dict = get_factura_emitida_dict(invoice, rectificativa=True)
        else:
            raise Exception('Unknown value in invoice.type')

        errors = invoice_model.validate(invoice_dict)
        if errors:
            raise Exception(
                'Errors were found while trying to validate the data:', errors)

        res = invoice_model.dump(invoice_dict)
        if res.errors:
            raise Exception(
                'Errors were found while trying to generate the dump:', errors)
        return res.data
