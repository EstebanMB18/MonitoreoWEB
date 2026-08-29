"""Consultas oficiales del monitoreo AWS.

Los nombres de claves se mantienen estables para no romper reportes ni históricos.
"""
COUNT_QUERIES = {
    # INTEROPPROD - pagos aprobados
    "aprob_creacion_payu": """fields @timestamp | filter OperationName = '/v1/payments - POST' | filter Description = 'Finaliza consumo Rest PayU Payment' | stats count(*) as count""",
    "aprob_creacion_ecollect": """fields @timestamp | filter OperationName = '/v1/payments - POST' | filter Description = 'Finaliza consumo Rest Ecollect' | stats count(*) as count""",
    "aprob_estado_payu": """fields @timestamp | filter OperationName = '/v1/payments - GET' | filter Description = 'Finaliza consumo Rest PayU' | stats count(*) as count""",
    "aprob_estado_ecollect": """fields @timestamp | filter OperationName = '/v1/payments - GET' | filter Description = 'Finaliza consumo Rest Ecollect' | stats count(*) as count""",
    "aprob_receiver": """fields @timestamp | filter OperationName = '/v1/receiver' | filter Description = 'Finaliza consumo WS.ERPAgent, notifyMultiPayments' or Description = 'Finaliza consumo BankAgent, invoiceMultiPayment' | stats count(*) as count""",

    # INTEROPPROD - pagos con error
    "err_creacion_payu": """fields @timestamp | filter OperationName = '/v1/payments - POST' | filter Description = 'Error consumo Rest PayU' | stats count(*) as count""",
    "err_creacion_ecollect": """fields @timestamp | filter OperationName = '/v1/payments - POST' | filter Description = 'Error Consumo Ecollect' | stats count(*) as count""",
    "err_estado_payu": """fields @timestamp | filter OperationName = '/v1/payments - GET' | filter Description = 'Error consumo Rest PayU' | stats count(*) as count""",
    "err_estado_ecollect": """fields @timestamp | filter OperationName = '/v1/payments - GET' | filter Description = 'Error Consumo Ecollect' | stats count(*) as count""",
    "err_receiver": """fields @timestamp | filter OperationName = '/v1/receiver' | filter Description = 'Error consumo WS.ERPAgent, notifyMultiPayments' or Description = 'Error consumo BankAgent, invoiceMultiPayment' or Description like /Error envio de notificación/ | stats count(*) as count""",
    "err_log": """fields @timestamp | filter LogLevel = 'Error' | stats count(*) as count""",
    "err_mongodb_update": """fields @timestamp | filter @message like /Error Update MongoDB/ | stats count(*) as count""",

    # Otros servicios INTEROPPROD existentes
    "seg_consulta_persona": """fields @timestamp | filter Description = 'Finaliza consumo servicio REST ConsultaPersona' | stats count(*) as count""",
    "error_cx": """fields @timestamp | filter Description = 'ERROR en el procesamiento de la creacion del archivo CX' | stats count(*) as count""",
    "tup_error": """fields @timestamp | filter ispresent(MessageOut) and LogLevel = 'Error' | stats count(*) as count""",
    "serviciosred_total": """fields @timestamp | stats count(*) as count""",

    # CSC
    "csc_task_timed": """fields @timestamp | filter @message like /Task timed/ | stats count(*) as count""",
    "csc_504": """fields @timestamp | filter @message like /504 Gateway Time-out/ | stats count(*) as count""",

    # MENSAJERÍA - log oficial API MENSAJERÍA
    "mens_timeout": """fields @timestamp | filter @message like /timeout/ | stats count(*) as count""",
    "mens_503": """fields @timestamp | filter @message like /503 Service Temporarily Unavailable/ | stats count(*) as count""",
    "mens_502": """fields @timestamp | filter @message like /502 Bad Gateway/ | stats count(*) as count""",
    "mens_report": """filter @type = 'REPORT' | stats count(*) as count""",
    "mens_cannot": """fields @timestamp | filter Httpcode != 200 and MessageIn.configS3.Broker = 'SD' | stats count(*) as count""",
    "mens_sms_failed": """fields @timestamp | filter MessageOut.resSMS.message like /SMS messsage failed to be sent/ | stats count(*) as count""",
    "mens_error_400_total": """fields @timestamp | filter Httpcode = 400 and OperationInvokerName in ['sendMessage','sendEMAIL','sendSMS','enviootp','EnviarSolicitud','ActualizarSolicitud'] | stats count(*) as count""",
    "mens_exitos_200_total": """fields @timestamp | filter Httpcode = 200 and OperationInvokerName in ['sendMessage','sendEMAIL','sendSMS','enviootp','EnviarSolicitud','ActualizarSolicitud'] | stats count(*) as count""",
    "otp_408": """fields @timestamp | filter Httpcode = 408 | stats count(*) as count""",

    # CORPORATIVO
    "replicador": """fields @timestamp | filter OperationName = '/replicar' | stats count(*) as count""",
    "otp_500": """fields @timestamp | filter message.Httpcode = '500' and message.OperationInvokerName = 'ValidarOTP' | stats count(*) as count""",
}

DETAIL_QUERIES = {
    "consulta_persona": """fields @timestamp, IdConsumer, IpInvoker, IdComponentTransaction, OperationName, Description, LogLevel, @message, MessageIn, MessageOut | filter Description = 'Finaliza consumo servicio REST ConsultaPersona' | sort @timestamp asc | limit 1000""",
    "mensajeria_errores": """fields @timestamp, IdConsumer, MessageIn.configS3.Broker, Httpcode, OperationInvokerName, MessageOut, MessageOut.error | filter Httpcode != 200 and OperationInvokerName in ['sendMessage','sendEMAIL','sendSMS','enviootp','EnviarSolicitud','ActualizarSolicitud'] | stats count(*) as count, min(@timestamp) as desde, max(@timestamp) as hasta by IdConsumer, MessageIn.configS3.Broker, Httpcode, OperationInvokerName, MessageOut, MessageOut.error | sort count desc""",
    "mensajeria_exitos": """fields @timestamp, IdConsumer, MessageIn.configS3.Broker, Httpcode, OperationInvokerName | filter Httpcode = 200 and OperationInvokerName in ['sendMessage','sendEMAIL','sendSMS','enviootp','EnviarSolicitud','ActualizarSolicitud'] | stats count(*) as count by IdConsumer, MessageIn.configS3.Broker, Httpcode, OperationInvokerName | sort count desc""",
    "mensajeria_400_por_hora": """fields @timestamp | filter Httpcode = 400 | stats count(*) as count by bin(1h) as hora | sort hora asc""",
    "mensajeria_200_por_hora": """fields @timestamp | filter Httpcode = 200 | stats count(*) as count by bin(1h) as hora | sort hora asc""",
    "tup_por_hora": """fields @timestamp | filter ispresent(MessageOut) and LogLevel = 'Error' | stats count(*) as count by bin(1h) as hora | sort hora asc""",
    "pagos_errores_por_hora": """fields @timestamp | filter Description = 'Error consumo Rest PayU' or Description = 'Error Consumo Ecollect' or Description = 'Error consumo WS.ERPAgent, notifyMultiPayments' or Description = 'Error consumo BankAgent, invoiceMultiPayment' or Description like /Error envio de notificación/ | stats count(*) as count by bin(1h) as hora | sort hora asc""",
    "replicador_por_hora": """fields @timestamp | filter OperationName = '/replicar' | stats count(*) as count by bin(1h) as hora | sort hora asc""",
    "serviciosred_resumen": """fields @timestamp | stats count(*) as count, max(@timestamp) as ultima_notificacion""",
    "serviciosred_por_hora": """fields @timestamp | stats count(*) as count by bin(1h) as hora | sort hora asc""",
    "serviciosred_10m": """fields @timestamp | stats count(*) as count by bin(10m) as hora | sort hora asc""",
}
