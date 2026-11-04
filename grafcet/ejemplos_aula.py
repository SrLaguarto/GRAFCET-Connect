"""Siete ejemplos breves de consulta, con entradas y salidas explícitas."""
from .builder import M


def marcha_paro():
    m=M().var('marcha').var('paro').var('motor','output').step('0',True).step('1')
    m.trans('t1',['0'],['1'],'marcha AND NOT paro').trans('t2',['1'],['0'],'paro').cont('1','motor')
    return m,{'0':(160,80),'t1':(160,140),'1':(160,200),'t2':(160,260)}


def eleccion():
    m=M().var('izquierda').var('derecha').var('fin').var('motor_izq','output').var('motor_der','output')
    m.step('0',True).step('1').step('2')
    m.trans('t1',['0'],['1'],'izquierda AND NOT derecha').trans('t2',['0'],['2'],'derecha AND NOT izquierda')
    m.trans('t3',['1'],['0'],'fin').trans('t4',['2'],['0'],'fin').cont('1','motor_izq').cont('2','motor_der')
    return m,{'0':(250,80),'t1':(120,140),'t2':(380,140),'1':(120,200),'2':(380,200),'t3':(120,280),'t4':(380,280)}


def simultaneidad():
    m=M().var('marcha').var('fin_izq').var('fin_der').var('motor_izq','output').var('motor_der','output')
    for s in ('0','1','2','3','4'):m.step(s,s=='0')
    m.trans('t1',['0'],['1','2'],'marcha').trans('t2',['1'],['3'],'fin_izq').trans('t3',['2'],['4'],'fin_der')
    m.trans('t4',['3','4'],['0'],'true').cont('1','motor_izq').cont('2','motor_der')
    return m,{'0':(250,60),'t1':(250,120),'1':(120,190),'2':(380,190),'t2':(120,250),'t3':(380,250),'3':(120,310),'4':(380,310),'t4':(250,380)}


def macroetapa():
    m=M().partial('GM').var('marcha').var('fin').var('motor','output')
    m.step('0',True).step('E',kind='entry',partial='GM').step('S',kind='exit',partial='GM')
    m.macro('M1','GM','E','S').trans('t1',['0'],['M1'],'marcha').trans('t2',['M1'],['0'],'true')
    m.trans('t3',['E'],['S'],'fin',partial='GM').cont('E','motor')
    return m,{'0':(120,80),'t1':(120,140),'M1':(120,200),'t2':(120,270),'E':(420,80),'t3':(420,140),'S':(420,200)}


def encapsulacion():
    m=M().partial('R').var('marcha').var('paro').var('fin').var('motor','output').var('luz','output')
    m.step('0',True).step('H',kind='enclosing').step('I',partial='R').step('J',partial='R')
    m.trans('t1',['0'],['H'],'marcha AND NOT paro').trans('t2',['H'],['0'],'paro')
    m.trans('t3',['I'],['J'],'fin',partial='R').cont('I','motor').cont('J','luz').enclosure('H','R',['I'])
    return m,{'0':(120,80),'t1':(120,140),'H':(120,200),'t2':(120,270),'I':(420,80),'t3':(420,140),'J':(420,200)}


def temporizacion():
    m=M().var('marcha').var('rearme').var('motor','output').var('luz','output')
    m.step('E0',True).step('E1').step('E2').trans('t1',['E0'],['E1'],'marcha')
    m.trans('t2',['E1'],['E2'],'delay(3 s, active(E1), 0 s)').trans('t3',['E2'],['E0'],'rearme')
    m.cont('E1','motor').cont('E2','luz')
    return m,{'E0':(160,60),'t1':(160,120),'E1':(160,180),'t2':(160,240),'E2':(160,300),'t3':(160,360)}


def repeticion():
    m=M().var('marcha').var('avance').var('repetir').var('fin').var('motor','output').var('luz','output')
    m.step('0',True).step('1').step('2').trans('t1',['0'],['1'],'marcha').trans('t2',['1'],['2'],'avance')
    m.trans('t3',['2'],['1'],'repetir').trans('t4',['2'],['0'],'fin AND NOT repetir').cont('1','motor').cont('2','luz')
    return m,{'0':(260,60),'t1':(260,120),'1':(260,180),'t2':(260,240),'2':(260,300),'t3':(60,360),'t4':(260,420)}


DIDACTICOS={
    'aula_marcha':('Marcha y paro','Marcha activa el motor. Paro lo detiene; tiene prioridad si se pulsan ambos.',marcha_paro),
    'aula_eleccion':('Elección de secuencia','Elige izquierda o derecha; fin vuelve al inicio. Ambas entradas juntas no eligen rama.',eleccion),
    'aula_simultaneidad':('Simultaneidad','Marcha inicia las dos ramas. Cada fin detiene su motor; se espera a que terminen ambas.',simultaneidad),
    'aula_macro':('Macroetapa','Marcha entra en M1. Fin completa la expansión y vuelve al inicio.',macroetapa),
    'aula_encapsulada':('Encapsulación','Marcha activa H y su recinto. Fin cambia motor por luz. Paro abandona H y vacía el recinto.',encapsulacion),
    'aula_temporizacion':('Temporización','Marcha activa el motor durante 3 s; después se enciende la luz. Rearme vuelve al inicio.',temporizacion),
    'aula_repeticion':('Repetición de secuencia','Marcha inicia; avance enciende la luz. Repetir vuelve al motor; fin termina si no se repite.',repeticion),
}
