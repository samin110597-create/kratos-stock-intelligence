from AlgorithmImports import *
from datetime import datetime, timedelta
from collections import deque

class ReportedPrice(PythonData):
    def get_source(self, config, date, is_live_mode):
        return SubscriptionDataSource('/kratos/prices/'+date.strftime('%Y-%m-%d')+'.csv', SubscriptionTransportMedium.LOCAL_FILE)
    def reader(self, config, line, date, is_live_mode):
        p=line.split(',')
        if len(p)!=3:return None
        item=ReportedPrice()
        item.symbol=config.symbol
        item.time=datetime.fromisoformat(p[0])
        item.end_time=item.time
        item.value=float(p[1])
        item['is_close']=int(p[2])
        return item

class ResearchFee(FeeModel):
    def get_order_fee(self, parameters):
        return OrderFee(CashAmount(abs(parameters.order.quantity)*parameters.security.price*0.001,'USD'))

class KratosResearch(QCAlgorithm):
    def initialize(self):
        start=datetime.fromisoformat(self.get_parameter('start'))
        end=datetime.fromisoformat(self.get_parameter('end'))
        self.set_start_date(start.year,start.month,start.day)
        self.set_end_date(end.year,end.month,end.day)
        self.set_cash(10000)
        self.set_time_zone(TimeZones.NEW_YORK)
        security=self.add_data(ReportedPrice,'RESEARCH',Resolution.MINUTE,fill_forward=False)
        self.symbol=security.symbol
        security.set_fee_model(ResearchFee())
        security.set_slippage_model(ConstantSlippageModel(0.0005))
        self.closes=deque(maxlen=30)
        self.desired=None
        self.last_above=None
        self.observations=0
    def on_data(self,data):
        if not data.contains_key(self.symbol):return
        bar=data[self.symbol]
        self.observations+=1
        if bar['is_close']:
            self.closes.append(float(bar.value))
            if len(self.closes)<30:return
            above=sum(list(self.closes)[-10:])/10>sum(self.closes)/30
            if self.last_above is not None and above!=self.last_above:
                self.desired=0.95 if above else 0
            self.last_above=above
        elif self.desired is not None:
            self.set_holdings(self.symbol,self.desired)
            self.desired=None
    def on_end_of_algorithm(self):
        self.set_runtime_statistic('Input observations',str(self.observations))
