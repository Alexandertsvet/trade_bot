from django.db import models

class TradeData(models.Model):
    """
    TradeStats

    https://apim.moex.com/iss/datashop/algopack/eq/tradestats/

    
    """
    
 
    # Основные поля с индексами
    tradedate = models.DateField(db_index=True, verbose_name="Дата сделки")
    tradetime = models.TimeField(db_index=True, verbose_name="время сделки")
    secid = models.CharField(max_length=36, db_index=True, verbose_name="код инструмента")  # bytes: 36
    
    # Ценовые данные (double → Decimal для точности)
    pr_open = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, verbose_name="цена открытия")
    pr_high = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, verbose_name="максимальная цена за период")
    pr_low = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, verbose_name="минимальная цена за период")
    pr_close = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, verbose_name="последняя цена за период")
    pr_std = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, verbose_name="стандартное отклонение цены")
    pr_vwap = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, verbose_name="взвешенная средняя цена")
    pr_change = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True, verbose_name="изменение цены за период, %")
    
    # Объемные показатели (int32, int64)
    vol = models.IntegerField(null=True, blank=True, verbose_name="объем в лотах")  # int32
    val = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, verbose_name="объем в рублях")  # double
    trades = models.IntegerField(null=True, blank=True, verbose_name="количество сделок")  # int32
    
    # Показатели по покупкам/продажам
    trades_b = models.IntegerField(null=True, blank=True, verbose_name="кол-во сделок на покупку")  # int32
    trades_s = models.IntegerField(null=True, blank=True, verbose_name="кол-во сделок на покупку")  # int32
    val_b = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, verbose_name="объем покупок в рублях")
    val_s = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, verbose_name="объем продаж в рублях")
    vol_b = models.BigIntegerField(null=True, blank=True, verbose_name="объем покупок в лотах")  # int64
    vol_s = models.BigIntegerField(null=True, blank=True, verbose_name="объем продаж в лотах")  # int64
    disb = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, verbose_name="соотношение объема покупок и продаж")
    pr_vwap_b = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, verbose_name="средневзвешенная цена покупки")
    pr_vwap_s = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True, verbose_name="средневзвешенная цена продажи")
    
    # Секундные данные (int32)
    systime = models.DateTimeField(db_index=True, verbose_name="время системы")  # datetime
    sec_pr_open = models.IntegerField(null=True, blank=True, verbose_name="кол-во секунд до pr_open")  # int32
    sec_pr_high = models.IntegerField(null=True, blank=True, verbose_name="кол-во секунд до pr_high")  # int32
    sec_pr_low = models.IntegerField(null=True, blank=True, verbose_name="кол-во секунд до pr_low")  # int32
    sec_pr_close = models.IntegerField(null=True, blank=True, verbose_name="кол-во секунд до pr_close")  # int32
    
    class Meta:
        db_table = 'trade_data'
        indexes = [
            models.Index(fields=['secid', 'tradedate', 'tradetime'], name='idx_secid_date_time'),
            models.Index(fields=['tradedate', 'tradetime'], name='idx_date_time'),
            models.Index(fields=['systime'], name='idx_systime'),
        ]
        # Уникальность для предотвращения дубликатов
        unique_together = [['secid', 'tradedate', 'tradetime']]
        ordering = [['tradedate', 'tradetime']]