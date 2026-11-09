"""Forecast comparison with rolling-origin selection and untouched final holdout.
Money stays in integer minor units. No model can guarantee future accuracy.
"""
from fractions import Fraction
import statistics

METHODS=('last_value','mean_last_3','seasonal_12')

def predict(series,horizon,method):
    if not series or any(type(v) is not int or v<0 for v in series):raise ValueError('Nonnegative integer monetary series required')
    if method=='last_value':return [series[-1]]*horizon
    if method=='mean_last_3':return [round(Fraction(sum(series[-3:]),len(series[-3:])))]*horizon
    if method=='seasonal_12':
        if len(series)<12:raise ValueError('Seasonal model needs 12 months')
        return [series[-12+i] for i in range(horizon)]
    raise ValueError('Unknown forecast method')

def scores(actual,predicted):
    residual=[a-p for a,p in zip(actual,predicted)]
    scale=sum(abs(a) for a in actual)
    return {'mae':float(Fraction(sum(abs(x) for x in residual),len(residual))),
            'wape_pct':float(Fraction(sum(abs(x) for x in residual)*100,scale)) if scale else None}

def evaluate(series_by_component,horizon):
    if type(horizon) is not int or not 1<=horizon<=6:raise ValueError('horizon must be 1..6')
    lengths={len(v) for v in series_by_component.values()}
    if len(lengths)!=1:raise ValueError('Components must have identical periods')
    length=next(iter(lengths));holdout_origin=length-horizon
    # Selection targets end before the untouched final holdout begins.
    origins=list(range(12,holdout_origin-horizon+1))[-24:]
    if len(origins)<6:raise ValueError(f'Insufficient validation history: need at least {17+2*horizon} consecutive approved months for horizon {horizon}')
    selection={};holdout={};future={};origin_predictions={}
    for component,values in series_by_component.items():
        if any(type(v) is not int or v<0 for v in values):raise ValueError('Invalid monetary component')
        candidates={}
        for method in METHODS:
            errors=[]
            for origin in origins:
                pred=predict(values[:origin],horizon,method)
                errors.extend(abs(a-b) for a,b in zip(values[origin:origin+horizon],pred))
            candidates[method]=float(Fraction(sum(errors),len(errors)))
        chosen=min(METHODS,key=lambda method:(candidates[method],METHODS.index(method)))
        selection[component]={'method':chosen,'rolling_selection_mae':candidates,'origins':len(origins)}
        test_pred=predict(values[:holdout_origin],horizon,chosen)
        holdout[component]=scores(values[holdout_origin:],test_pred)
        future[component]=predict(values,horizon,chosen)
        origin_predictions[component]=test_pred
    revenue_key=next(iter(series_by_component))
    costs=[key for key in series_by_component if key!=revenue_key]
    actual_profit=[series_by_component[revenue_key][i]-sum(series_by_component[k][i] for k in costs) for i in range(holdout_origin,length)]
    pred_profit=[origin_predictions[revenue_key][i]-sum(origin_predictions[k][i] for k in costs) for i in range(horizon)]
    profit_score=scores(actual_profit,pred_profit)
    warnings=[]
    revenue_score=holdout[revenue_key]
    if revenue_score['wape_pct'] is None:warnings.append('Holdout revenue is zero; WAPE is undefined')
    elif revenue_score['wape_pct']>30:warnings.append('Holdout revenue WAPE exceeds 30%; review before planning')
    for key,values in series_by_component.items():
        previous=statistics.mean(values[:-3]);recent=statistics.mean(values[-3:])
        if previous and (recent/previous>1.5 or recent/previous<0.5):warnings.append(f'{key}: recent level changed materially; review structural change')
    return {'selection':selection,'future':future,'holdout':holdout,'profit_holdout':profit_score,
        'selection_origins':origins,'holdout_origin':holdout_origin,'warnings':warnings,
        'validation_note':'Model chosen only on rolling-origin selection data; final horizon-sized block excluded from selection. Scores are historical, not a guarantee.',
        'uncertainty_note':'No calibrated prediction interval; a short final holdout is insufficient to establish reliable future coverage.'}
