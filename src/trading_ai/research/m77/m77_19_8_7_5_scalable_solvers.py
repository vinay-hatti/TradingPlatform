from __future__ import annotations
import numpy as np
from dataclasses import dataclass

def soft_threshold(x,t):
    x=np.asarray(x,dtype=float)
    return np.sign(x)*np.maximum(np.abs(x)-t,0.0)

def pinball_prox(v,lam,q):
    v=np.asarray(v,dtype=float)
    hi=lam*q
    lo=lam*(q-1.0)
    out=np.zeros_like(v)
    out[v>hi]=v[v>hi]-hi
    out[v<lo]=v[v<lo]-lo
    return out

@dataclass
class ADMMElasticNetQuantile:
    quantile:float=0.5
    alpha:float=0.001
    l1_ratio:float=0.5
    rho:float=1.0
    max_iter:int=5000
    cd_max_iter:int=200
    tol:float=1e-6

    def fit(self,X,y):
        X=np.asarray(X,dtype=float);y=np.asarray(y,dtype=float)
        n,p=X.shape
        q=float(self.quantile);a=float(self.alpha);l1r=float(self.l1_ratio);rho=float(self.rho)
        if not (0<q<1): raise ValueError("quantile")
        if a<0 or not (0<=l1r<=1): raise ValueError("penalty")
        if rho<=0: raise ValueError("rho")

        xm=X.mean(axis=0)
        Xc=X-xm
        x2=np.sum(Xc*Xc,axis=0)
        beta=np.zeros(p,dtype=float)
        intercept=float(np.quantile(y,q))
        r=y-(intercept+X@beta)
        u=np.zeros(n,dtype=float)

        lam1=a*l1r
        lam2=a*(1.0-l1r)
        prev_r=r.copy()
        converged=False
        primal_norm=float("inf");dual_norm=float("inf")

        for it in range(self.max_iter):
            v=y-(intercept+X@beta)+u
            r=pinball_prox(v,1.0/(rho*n),q)

            z=y-r+u
            zmean=float(z.mean())
            zc=z-zmean
            pred=Xc@beta
            for _ in range(self.cd_max_iter):
                old=beta.copy()
                for j in range(p):
                    partial=zc-(pred-Xc[:,j]*beta[j])
                    numer=rho*np.dot(Xc[:,j],partial)
                    denom=rho*x2[j]+lam2
                    new=0.0 if denom<=0 else float(soft_threshold(numer,lam1)/denom)
                    pred += Xc[:,j]*(new-beta[j])
                    beta[j]=new
                if np.max(np.abs(beta-old)) <= self.tol*(1.0+np.max(np.abs(old))):
                    break
            intercept=zmean-float(np.dot(xm,beta))

            primal=y-(intercept+X@beta)-r
            u=u+primal

            primal_norm=float(np.linalg.norm(primal))
            dual_norm=float(rho*np.linalg.norm(r-prev_r))
            scale=max(1.0,float(np.linalg.norm(y)),float(np.linalg.norm(r)))
            if primal_norm<=self.tol*scale and dual_norm<=self.tol*scale:
                converged=True
                break
            prev_r=r.copy()

        self.coef_=beta
        self.intercept_=intercept
        self.n_iter_=it+1
        self.converged_=converged
        self.primal_residual_norm_=primal_norm
        self.dual_residual_norm_=dual_norm
        return self

    def predict(self,X):
        X=np.asarray(X,dtype=float)
        return self.intercept_+X@self.coef_

PrimalDualElasticNetQuantile=ADMMElasticNetQuantile
