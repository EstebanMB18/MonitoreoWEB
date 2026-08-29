def datos_demo():
    return {
      "metricas":{
        "aprob_creacion_payu":1805,"aprob_creacion_ecollect":5666,"aprob_estado_payu":3037,"aprob_estado_ecollect":24539,"aprob_receiver":5295,
        "err_creacion_payu":0,"err_creacion_ecollect":8,"err_estado_payu":0,"err_estado_ecollect":0,"err_receiver":0,"err_log":8,"err_mongodb_update":0,
        "seg_consulta_persona":440,"error_cx":0,"tup_error":117,"csc_task_timed":0,"csc_504":0,
        "mens_timeout":2,"mens_503":0,"mens_502":0,"mens_report":47478,"mens_total_send":47478,"mens_cannot":4,"mens_sms_failed":1,"mens_error_400_total":146,"mens_exitos_200_total":47320,
        "replicador":4543,"otp_500":0,"otp_408":0},
      "detalles":{
        "consulta_persona":[],
        "mensajeria_errores":[
          {"IdConsumer":"MC","MessageIn.configS3.Broker":"MC","Httpcode":"400","OperationInvokerName":"sendEMAIL","MessageOut.error":"Dato inválido","count":"130","desde":"2026-07-10 13:46","hasta":"2026-07-10 17:14"},
          {"IdConsumer":"IF","MessageIn.configS3.Broker":"IF","Httpcode":"500","OperationInvokerName":"sendSMS","MessageOut.error":"Internal Server Error","count":"3","desde":"2026-07-10 15:52","hasta":"2026-07-10 16:51"}],
        "mensajeria_exitos":[],
        "mensajeria_400_por_hora":[{"hora":"13:00","count":2},{"hora":"14:00","count":5},{"hora":"15:00","count":12},{"hora":"16:00","count":7},{"hora":"17:00","count":3}],
        "mensajeria_200_por_hora":[{"hora":"13:00","count":8200},{"hora":"14:00","count":9100},{"hora":"15:00","count":10400},{"hora":"16:00","count":9800},{"hora":"17:00","count":9820}],
        "tup_por_hora":[{"hora":"13:00","count":10},{"hora":"14:00","count":22},{"hora":"15:00","count":59},{"hora":"16:00","count":16},{"hora":"17:00","count":10}],
        "pagos_errores_por_hora":[{"hora":"13:00","count":0},{"hora":"14:00","count":2},{"hora":"15:00","count":3},{"hora":"16:00","count":2},{"hora":"17:00","count":1}],
        "replicador_por_hora":[{"hora":"13:00","count":830},{"hora":"14:00","count":940},{"hora":"15:00","count":970},{"hora":"16:00","count":901},{"hora":"17:00","count":902}]},
      "errores_consulta":[]}
