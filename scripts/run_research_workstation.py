import argparse, uvicorn
def main():
    p=argparse.ArgumentParser(); p.add_argument("--host",default="127.0.0.1"); p.add_argument("--port",type=int,default=8000); p.add_argument("--reload",action="store_true"); a=p.parse_args()
    uvicorn.run("trading_ai.ui.research_workstation_app:app",host=a.host,port=a.port,reload=a.reload)
if __name__=="__main__": main()
