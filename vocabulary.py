"""Description vocabulary. No price, identifier, or label inputs."""
import re

ALIAS_GROUPS = '''
advanced adv
ambulatory amb
assisted asst
bedside beds
comprehensive compr
continuous cont
elective elect
emergency emer
extended ext
focused foc
inpatient inpt
intensive intens
intermittent interm
outpatient outpt
postoperative postop
preoperative preop
routine rtn
specialist spclst
standard std
supervised supv
cardiac card
haematology haem
infectious infect
metabolic metab
neurological neuro
rheumatologic rheum
immunologic immun
musculoskeletal msk
ophthalmic ophth
psychiatric psych
pulmonary pulm
urologic urol
gastrointestinal gi
geriatric ger
otolaryngologic ent
oncology onc
obstetric obst
vascular vasc
dermatologic derm
orthopaedic ortho
renal ren
palliative pall
endocrine endo
hepatic hep
paediatric paed
recovery recov
room rm
occupancy occ
physiotherapy physio
session sess
critical crit
care cr
anaesthesia anaes
administration admin
nursing nurs
observation obs
consultation consult
laboratory lab
panel pnl
home hm
visit vst
endoscopic endosc
procedure proc
ward wd
bed bd
case cs
conference conf
dialysis dial
imaging img
interpretation interp
infusion inf
therapy ther
discharge disch
planning plng
theatre thtr
time tm
biopsy biop
rehabilitation rehab
programme prog
transfusion transf
service svc
transport transp
wound wnd
telemetry telem
monitoring monit
pharmaceutical pharm
dispensing disp
nutritional nutr
support supp
radiotherapy radiother
fraction fract
isolation isol
specimen spcm
analysis anly
diagnostic diag
ventilation vent
sterilisation steril
'''
ALIASES = {}
for group in ALIAS_GROUPS.strip().splitlines():
    words = group.split()
    ALIASES.update({word: words[0] for word in words})


def tokens(description):
    text = re.sub(r'/[a-z]+-\d+', '', str(description).lower())
    return {ALIASES.get(word, word) for word in re.findall(r'[a-z]+', text)}


