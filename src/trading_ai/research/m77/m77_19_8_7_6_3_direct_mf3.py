from __future__ import annotations
import time
from dataclasses import dataclass
import numpy as np

def soft_threshold(x,t):
    x=np.asarray(x,dtype=float)
    return np.sign(x)*np.maximum(np.abs(x)-t,0.0)

def pinball_loss(y,p,q):
    r=np.asarray(y,dtype=float)-np.asarray(p,dtype=float)
    return float(np.where(r>=0,q*r,(q-1.0)*r).mean())

def exact_objective(X,y,beta,intercept,q,alpha,l1_ratio):
    pred=float(intercept)+np.asarray(X,dtype=float)@np.asarray(beta,dtype=float)
    return pinball_loss(y,pred,q)+float(alpha*(l1_ratio*np.abs(beta).sum()+(1.0-l1_ratio)*0.5*np.dot(beta,beta)))

@dataclass
class DirectProximalSubgradientQuantile:
    quantile:float=0.5
    alpha:float=0.001
    l1_ratio:float=0.5
    max_iter:int=4000
    tol:float=2e-6
    initial_step:float=0.25
    progress_every:int=100

    def fit(self,X,y,progress_callback=None):
        X=np.asarray(X,dtype=float,order="C")
        y=np.asarray(y,dtype=float)
        n,p=X.shape
        q=float(self.quantile); a=float(self.alpha); r=float(self.l1_ratio)
        if not (0<q<1): raise ValueError("quantile")
        if a<0 or not (0<=r<=1): raise ValueError("penalty")

        beta=np.zeros(p,dtype=float)
        intercept=float(np.quantile(y,q))
        best_beta=beta.copy();best_intercept=intercept
        best_obj=exact_objective(X,y,beta,intercept,q,a,r)
        grad_sq_acc=1e-12
        t0=time.perf_counter()
        matvec_seconds=0.0
        converged=False
        stale=0

        for it in range(1,self.max_iter+1):
            tm=time.perf_counter()
            pred=intercept+X@beta
            matvec_seconds += time.perf_counter()-tm
            resid=y-pred
            # Subgradient wrt prediction.
            s=np.where(resid>0.0,-q,np.where(resid<0.0,1.0-q,0.0))
            gb=(X.T@s)/n + a*(1.0-r)*beta
            gi=float(np.mean(s))
            g2=float(np.dot(gb,gb)+gi*gi)
            grad_sq_acc += g2
            step=float(self.initial_step/np.sqrt(grad_sq_acc))

            beta_new=soft_threshold(beta-step*gb,step*a*r)
            intercept_new=intercept-step*gi

            obj=exact_objective(X,y,beta_new,intercept_new,q,a,r)
            if obj < best_obj - 1e-12:
                best_obj=obj;best_beta=beta_new.copy();best_intercept=float(intercept_new);stale=0
            else:
                stale+=1

            delta=max(float(np.max(np.abs(beta_new-beta))) if p else 0.0,abs(intercept_new-intercept))
            beta=beta_new;intercept=float(intercept_new)

            if progress_callback and (it==1 or it%self.progress_every==0):
                progress_callback({
                    "iteration":it,
                    "exact_objective":best_obj,
                    "step_size":step,
                    "delta":delta,
                    "elapsed_seconds":time.perf_counter()-t0,
                })

            if delta<=self.tol*(1.0+max(abs(intercept),float(np.max(np.abs(beta))) if p else 0.0)) and stale>=20:
                converged=True
                break

        self.coef_=best_beta
        self.intercept_=best_intercept
        self.objective_=best_obj
        self.n_iter_=it
        self.converged_=converged
        self.elapsed_seconds_=time.perf_counter()-t0
        self.matvec_seconds_=matvec_seconds
        return self

    def predict(self,X):
        X=np.asarray(X,dtype=float)
        return self.intercept_+X@self.coef_
