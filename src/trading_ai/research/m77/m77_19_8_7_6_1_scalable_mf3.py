from __future__ import annotations
import time
from dataclasses import dataclass
import numpy as np
from sklearn.linear_model import ElasticNet, Lasso, Ridge

def pinball_prox(v, lam, q):
    v=np.asarray(v,dtype=float)
    hi=lam*q
    lo=lam*(q-1.0)
    out=np.zeros_like(v)
    gt=v>hi; lt=v<lo
    out[gt]=v[gt]-hi
    out[lt]=v[lt]-lo
    return out

def _safe_n_iter(model):
    value=getattr(model,"n_iter_",None)
    if value is None:
        return 1
    try:
        return int(value)
    except Exception:
        return 1

@dataclass
class CompiledADMMElasticNetQuantile:
    quantile:float=0.5
    alpha:float=0.001
    l1_ratio:float=0.5
    rho:float=1.0
    max_iter:int=2000
    tol:float=2e-6
    enet_max_iter:int=3000
    enet_tol:float=1e-5

    def _make_inner_solver(self,n):
        a=float(self.alpha); r=float(self.l1_ratio); rho=float(self.rho)
        if r==0.0:
            return Ridge(alpha=a/rho,fit_intercept=True,solver="auto"),"RIDGE"
        if r==1.0:
            return Lasso(alpha=a/(rho*n),fit_intercept=True,max_iter=self.enet_max_iter,
                         tol=self.enet_tol,warm_start=True,selection="cyclic"),"LASSO"
        return ElasticNet(alpha=a/(rho*n),l1_ratio=r,fit_intercept=True,
                          max_iter=self.enet_max_iter,tol=self.enet_tol,
                          selection="cyclic",warm_start=True,precompute=False),"ELASTIC_NET"

    def fit(self,X,y,progress_callback=None):
        X=np.asarray(X,dtype=float,order="C")
        y=np.asarray(y,dtype=float)
        n,p=X.shape
        q=float(self.quantile);a=float(self.alpha);r=float(self.l1_ratio);rho=float(self.rho)
        if not (0<q<1): raise ValueError("quantile")
        if a<0 or not (0<=r<=1): raise ValueError("penalty")
        if rho<=0: raise ValueError("rho")

        beta=np.zeros(p,dtype=float)
        intercept=float(np.quantile(y,q))
        residual=y-(intercept+X@beta)
        u=np.zeros(n,dtype=float)
        prev_residual=residual.copy()

        model,inner_solver_name=self._make_inner_solver(n)
        converged=False
        t0=time.perf_counter()
        matvec_seconds=0.0
        inner_solver_seconds=0.0
        prox_seconds=0.0
        primal_norm=float("inf")
        dual_norm=float("inf")

        for it in range(self.max_iter):
            tm=time.perf_counter()
            xb=intercept+X@beta
            matvec_seconds += time.perf_counter()-tm

            tp=time.perf_counter()
            v=y-xb+u
            residual=pinball_prox(v,1.0/(rho*n),q)
            prox_seconds += time.perf_counter()-tp

            target=y-residual+u
            if inner_solver_name in ("LASSO","ELASTIC_NET") and it>0:
                model.coef_=beta.copy()
                model.intercept_=intercept

            ti=time.perf_counter()
            model.fit(X,target)
            inner_solver_seconds += time.perf_counter()-ti
            beta=np.asarray(model.coef_,dtype=float).copy()
            intercept=float(model.intercept_)

            tm=time.perf_counter()
            primal=y-(intercept+X@beta)-residual
            matvec_seconds += time.perf_counter()-tm
            u=u+primal

            primal_norm=float(np.linalg.norm(primal))
            dual_norm=float(rho*np.linalg.norm(residual-prev_residual))
            scale=max(1.0,float(np.linalg.norm(y)),float(np.linalg.norm(residual)))

            if progress_callback and (it==0 or (it+1)%25==0):
                progress_callback({
                    "iteration":it+1,
                    "primal_residual_norm":primal_norm,
                    "dual_residual_norm":dual_norm,
                    "elapsed_seconds":time.perf_counter()-t0,
                    "inner_solver":inner_solver_name,
                    "inner_iterations":_safe_n_iter(model),
                })

            if primal_norm<=self.tol*scale and dual_norm<=self.tol*scale:
                converged=True
                break
            prev_residual=residual.copy()

        self.coef_=beta
        self.intercept_=intercept
        self.n_iter_=it+1
        self.converged_=converged
        self.primal_residual_norm_=primal_norm
        self.dual_residual_norm_=dual_norm
        self.elapsed_seconds_=time.perf_counter()-t0
        self.matvec_seconds_=matvec_seconds
        self.elastic_net_seconds_=inner_solver_seconds
        self.inner_solver_seconds_=inner_solver_seconds
        self.prox_seconds_=prox_seconds
        self.enet_last_n_iter_=_safe_n_iter(model)
        self.inner_solver_name_=inner_solver_name
        return self

    def predict(self,X):
        X=np.asarray(X,dtype=float)
        return self.intercept_+X@self.coef_
