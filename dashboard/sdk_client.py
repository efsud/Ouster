"""Observable wrapper around supplied SDK 3.1.0; vendor files stay unchanged."""
import logging
import time
import requests
from realtime_subscriber.Realtime_subscriber_api import BCTWSConnection
from .storage import Store

class HealthHandler(logging.Handler):
    def __init__(self,path,site):
        super().__init__();self.path=path;self.site=site
    def emit(self,record):
        message=str(record.msg)
        codes=['UNAUTHENTICATED','PERMISSION_DENIED','UNAVAILABLE','DEADLINE_EXCEEDED']
        code=next((x for x in codes if x in message),None)
        if code:Store(self.path).set_health(self.site,state='stream_error',error='grpc_'+code.lower())
        elif record.levelno>=logging.ERROR and 'authentication' not in message.lower():
            Store(self.path).set_health(self.site,state='stream_error',error='sdk_transport_error')

class ObservableConnection(BCTWSConnection):
    def __init__(self,*args,store_path,site_id,**kwargs):
        self.store_path=store_path;self.site_id=site_id
        super().__init__(*args,**kwargs)
    def health(self,**fields):Store(self.store_path).set_health(self.site_id,**fields)
    def createLogger(self):
        self.logger=logging.getLogger('ouster.sdk.'+self.site_id)
        self.logger.setLevel(logging.INFO);self.logger.propagate=False
        if not self.logger.handlers:self.logger.addHandler(HealthHandler(self.store_path,self.site_id))
    def getToken(self):
        self.health(state='authenticating',error=None)
        try:
            response=requests.post(self.auth_server_access,json={'username':self.username,'password':self.password},timeout=20,allow_redirects=False)
            if response.status_code!=200:
                self.health(state='authentication_failed',error=f'auth_http_{response.status_code}');return False
            data=response.json();self.token=data['access'];self.refresh=data['refresh']
            self.health(state='authenticated',error=None);return True
        except requests.RequestException:
            self.health(state='authentication_failed',error='auth_network_error');return False
        except (ValueError,KeyError):
            self.health(state='authentication_failed',error='auth_invalid_response');return False
    def refreshToken(self):
        try:
            response=requests.post(self.auth_server_refresh,json={'refresh':self.refresh},timeout=20,allow_redirects=False)
            if response.status_code==200:self.token=response.json()['access'];return True
        except (requests.RequestException,ValueError,KeyError):pass
        self.health(state='authentication_failed',error='token_refresh_failed');return False
    def getCredentials_beacon(self):
        while self.serverAdd is None:
            self.health(state='routing',error=None)
            try:
                response=requests.post(self.beaconAddress+'route',json={'UDID':self.UDID,'type':'2','token':self.token},timeout=20,allow_redirects=False)
                if response.status_code==200:
                    data=response.json();self.serverAdd=data['address'];self.crt=data['key'].encode()
                    self.health(state='awaiting_events',error=None);return
                self.health(state='routing_failed',error=f'beacon_http_{response.status_code}')
            except requests.RequestException:self.health(state='routing_failed',error='beacon_network_error')
            except (ValueError,KeyError):self.health(state='routing_failed',error='beacon_invalid_response')
            time.sleep(5)
