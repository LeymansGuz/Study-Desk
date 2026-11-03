"""Managed web process. Tokens arrive through the environment, never arguments."""
import os,sys,logging.config
from local_app import ROOT,RUNTIME,private_json,fingerprint

if __name__=='__main__':
    port=int(sys.argv[1]);instance=sys.argv[2]
    if os.environ.get('STUDY_LOCAL_INSTANCE')!=instance:raise SystemExit('Use the local start command.')
    os.chdir(ROOT)
    private_json(RUNTIME/'web.json',{'pid':os.getpid(),'birth':fingerprint(os.getpid()),'instance':instance})
    logging.config.dictConfig({'version':1,'disable_existing_loggers':False,
        'formatters':{'plain':{'format':'%(asctime)s %(levelname)s %(name)s %(message)s'}},
        'handlers':{'file':{'class':'logging.handlers.RotatingFileHandler','filename':str(RUNTIME/'web-runtime.log'),
                           'maxBytes':5*1024*1024,'backupCount':3,'encoding':'utf-8','formatter':'plain'}},
        'root':{'handlers':['file'],'level':'INFO'},
        'loggers':{'uvicorn':{'handlers':['file'],'level':'INFO','propagate':False}}})
    import uvicorn
    import app
    server=uvicorn.Server(uvicorn.Config(app.app,host='127.0.0.1',port=port,proxy_headers=False,
                                       timeout_graceful_shutdown=20,access_log=False,log_config=None))
    app.app.state.local_shutdown=lambda:setattr(server,'should_exit',True)
    server.run()
