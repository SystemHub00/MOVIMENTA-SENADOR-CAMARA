import os
import re
import traceback
import uuid
from datetime import datetime
from urllib.parse import quote
from flask import Flask, redirect, render_template_string, request, session, url_for
from gsheet_utils import append_to_sheet
ALLOWED_EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9_.+-]+@((gmail|hotmail|outlook|yahoo)\.(com|com\.br))$",
    re.IGNORECASE,
)
NAME_PATTERN = re.compile(r"[A-Za-z\u00C0-\u00FF '\u00b4`^~.-]+")
VALID_DDDS = {
    "11", "12", "13", "14", "15", "16", "17", "18", "19",
    "21", "22", "24", "27", "28",
    "31", "32", "33", "34", "35", "37", "38",
    "41", "42", "43", "44", "45", "46", "47", "48", "49",
    "51", "53", "54", "55",
    "61", "62", "63", "64", "65", "66", "67", "68", "69",
    "71", "73", "74", "75", "77", "79",
    "81", "82", "83", "84", "85", "86", "87", "88", "89",
    "91", "92", "93", "94", "95", "96", "97", "98", "99",
}
# ── LOCAIS ───────────────────────────────────────────────────────────────────
LOCAL_OPTIONS = [
    {"id": "1", "nome": "MARCO 7 - SENADOR CAMA\u00c1 \u2014 SALA 1"},
]
# ── CATÁLOGO DE CURSOS (com EAD) ─────────────────────────────────────────────
COURSE_CATALOG = [
    {"id": "1", "local_id": "1", "nome": "ATENDENTE DE SAL\u00c3O DE CAF\u00c9 DA MANH\u00c3 (EAD)"},
    {"id": "2", "local_id": "1", "nome": "ORIENTADOR DE HOTELARIA (EAD)"},
    {"id": "3", "local_id": "1", "nome": "AUXILIAR ADMINISTRATIVO (EAD)"},
    {"id": "4", "local_id": "1", "nome": "SOCIAL MEDIA (EAD)"},
    {"id": "5", "local_id": "1", "nome": "MARKETING DIGITAL (EAD)"},
]
# ── TURMAS ───────────────────────────────────────────────────────────────────
TURMA_OPTIONS = [
    {"id": "1", "local_id": "1", "curso_id": "1", "turma_codigo": "01",
     "agenda_id": "1", "periodo_id": "1", "encerramento_id": "1", "endereco_id": "1"},
    {"id": "2", "local_id": "1", "curso_id": "2", "turma_codigo": "01",
     "agenda_id": "2", "periodo_id": "1", "encerramento_id": "1", "endereco_id": "1"},
    {"id": "3", "local_id": "1", "curso_id": "3", "turma_codigo": "01",
     "agenda_id": "3", "periodo_id": "2", "encerramento_id": "2", "endereco_id": "1"},
    {"id": "4", "local_id": "1", "curso_id": "4", "turma_codigo": "01",
     "agenda_id": "4", "periodo_id": "2", "encerramento_id": "2", "endereco_id": "1"},
    {"id": "5", "local_id": "1", "curso_id": "5", "turma_codigo": "01",
     "agenda_id": "5", "periodo_id": "2", "encerramento_id": "2", "endereco_id": "1"},
]
# ── HORÁRIOS — todos EAD: vazios ─────────────────────────────────────────────
SCHEDULE_OPTIONS = {
    "1": {"dias_aula": "", "horario": ""},
    "2": {"dias_aula": "", "horario": ""},
    "3": {"dias_aula": "", "horario": ""},
    "4": {"dias_aula": "", "horario": ""},
    "5": {"dias_aula": "", "horario": ""},
}
# ── DATAS DE INÍCIO — todas EAD: vazias ──────────────────────────────────────
START_DATE_OPTIONS = {
    "1": "",
    "2": "",
}
# ── DATAS DE ENCERRAMENTO ────────────────────────────────────────────────────
END_DATE_OPTIONS = {
    "1": "28/09/2026",
    "2": "25/09/2026",
}
# ── ENDEREÇOS ────────────────────────────────────────────────────────────────
ADDRESS_OPTIONS = {
    "1": "\U0001f4cdBloco D'jorge do Marco Sete - Rua Marco Sete, n\u00b0102, Senador Cama\u00e1 - CEP: 21833-325",
}
def build_course_options():
    local_by_id  = {o["id"]: o for o in LOCAL_OPTIONS}
    course_by_id = {o["id"]: o for o in COURSE_CATALOG}
    result = []
    for t in TURMA_OPTIONS:
        local    = local_by_id[t["local_id"]]
        course   = course_by_id[t["curso_id"]]
        schedule = SCHEDULE_OPTIONS[t["agenda_id"]]
        result.append({
            "id":             t["id"],
            "local_id":       t["local_id"],
            "curso_id":       t["curso_id"],
            "local":          local["nome"],
            "curso":          course["nome"],
            "turma":          f"{course['nome']} - TURMA {t['turma_codigo']}",
            "dias_aula":      schedule["dias_aula"],
            "horario":        schedule["horario"],
            "data_inicio":    START_DATE_OPTIONS[t["periodo_id"]],
            "encerramento":   END_DATE_OPTIONS[t["encerramento_id"]],
            "endereco_curso": ADDRESS_OPTIONS[t["endereco_id"]],
        })
    return result
COURSE_OPTIONS       = build_course_options()
LOCAL_OPTIONS_BY_ID  = {o["id"]: o for o in LOCAL_OPTIONS}
COURSE_CATALOG_BY_ID = {o["id"]: o for o in COURSE_CATALOG}
COURSE_OPTIONS_BY_ID = {o["id"]: o for o in COURSE_OPTIONS}
COURSE_INFO          = COURSE_OPTIONS[0]
def build_whatsapp_share_url(home_url):
    message = (
        "Acabei de me inscrever em uma oportunidade de qualificacao profissional. "
        f"Confira aqui: {home_url}"
    )
    return f"https://wa.me/?text={quote(message)}"
def get_course_option(option_id):
    return COURSE_OPTIONS_BY_ID.get(str(option_id or ""))
def get_local_option(local_id):
    return LOCAL_OPTIONS_BY_ID.get(str(local_id or ""))
def get_course_catalog_option(course_id):
    return COURSE_CATALOG_BY_ID.get(str(course_id or ""))
def fill_form_data_from_option(form_data, option):
    for k in ("local_id","curso_id","local","curso","turma",
              "dias_aula","horario","data_inicio","encerramento","endereco_curso"):
        form_data[k] = option[k]
def fill_form_data_from_selection(form_data):
    sel_local  = get_local_option(form_data.get("local_id"))
    sel_course = get_course_catalog_option(form_data.get("curso_id"))
    sel_option = get_course_option(form_data.get("opcao_id"))
    if sel_local:
        form_data["local"] = sel_local["nome"]
    if sel_course and sel_course["local_id"] == form_data.get("local_id"):
        form_data["curso"] = sel_course["nome"]
    if sel_option:
        fill_form_data_from_option(form_data, sel_option)
TEMPLATE_WIZARD = r'''
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Movimenta Rio - Cristiane</title>
    <link rel="stylesheet" href="/static/style.css">
    <link rel="stylesheet" href="/static/assistant.css">
    <link href="https://fonts.googleapis.com/css2?family=Wise:wght@400;700;900&display=swap" rel="stylesheet">
    <script>
        !function(f,b,e,v,n,t,s)
        {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
        n.callMethod.apply(n,arguments):n.queue.push(arguments)};
        if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
        n.queue=[];t=b.createElement(e);t.async=!0;
        t.src=v;s=b.getElementsByTagName(e)[0];
        s.parentNode.insertBefore(t,s)}(window, document,'script',
        'https://connect.facebook.net/en_US/fbevents.js');
        fbq('init', '2008632536670997');
        fbq('track', 'PageView');
    </script>
    <style>
        :root{--cor-principal:#1155cc;--cor-principal-escura:#0d47a1;--cor-clara:#eef4ff;--cor-texto:#17386d;--cor-borda:#a8c0f4;--sombra-card:0 18px 55px rgba(17,85,204,0.18);}
        *{box-sizing:border-box}html,body{min-height:100%;margin:0;padding:0}
        body{min-height:100vh;background:radial-gradient(circle at top left,rgba(17,85,204,0.14),transparent 34%),radial-gradient(circle at top right,rgba(211,226,255,0.82),transparent 32%),linear-gradient(135deg,#f5f9ff 0%,#fff 42%,#dfeaff 100%);color:var(--cor-texto);font-family:'Wise',Arial,sans-serif;}
        .main-header{border-bottom:4px solid var(--cor-principal);background:rgba(255,255,255,0.92);backdrop-filter:blur(8px)}
        .wizard-page{width:min(900px,98vw);margin:0 auto;padding:8px 0 18px;text-align:center}
        .wizard-progress{margin:18px auto 22px;padding:18px 18px 20px;border-radius:28px;background:rgba(255,255,255,0.9);box-shadow:0 12px 30px rgba(17,85,204,0.12)}
        .wizard-track{width:100%;height:14px;background:#dbe6fb;border-radius:999px;overflow:hidden}
        .wizard-fill{height:100%;width:25%;background:linear-gradient(90deg,#1155cc 0%,#4f86ea 100%);border-radius:999px;transition:width .3s ease}
        .wizard-labels{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}
        .wizard-label{padding:12px 10px;border:1px solid #c9daf8;border-radius:18px;background:#fff;color:#2f5fb4;font-size:.92rem;font-weight:700;text-align:center;transition:all .25s ease}
        .wizard-label.ativo{border-color:var(--cor-principal);background:var(--cor-clara);color:var(--cor-principal)}
        .wizard-shell{background:rgba(255,255,255,0.88);border:1px solid rgba(255,255,255,0.9);border-radius:34px;box-shadow:var(--sombra-card);overflow:hidden}
        .wizard-panel[data-step="index"] .hero-card,.wizard-panel[data-step="dados"] .step-card,.wizard-panel[data-step="escolher"] .step-card,.wizard-panel[data-step="revisao"] .step-card{max-width:760px;margin:0 auto}
        .wizard-panel{display:none;padding:18px 8px;animation:surgir .28s ease}
        .wizard-panel.ativo{display:block}
        @keyframes surgir{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
        .hero-grid{display:grid;grid-template-columns:minmax(0,1fr);gap:14px;align-items:center;justify-items:center}
        .hero-card{padding:32px;border-radius:30px;background:linear-gradient(135deg,#fff 0%,#f5f9ff 58%,#dfeaff 100%);border:1px solid #c9daf8;width:100%;text-align:center}
        .hero-pill{display:inline-flex;align-items:center;gap:8px;padding:10px 18px;border-radius:999px;background:var(--cor-principal);color:#fff;font-size:.95rem;font-weight:800;letter-spacing:.05em;text-transform:uppercase}
        .hero-title,.panel-title{margin:18px 0 10px;color:var(--cor-principal);font-size:clamp(2rem,3.8vw,3.2rem);line-height:1;letter-spacing:-.04em}
        .panel-title{font-size:clamp(1.7rem,3vw,2.4rem)}
        .hero-subtitle,.panel-subtitle{margin:0;color:#2f5fb4;font-size:1.05rem;line-height:1.55}
        .hero-highlights{display:grid;gap:10px;margin-top:16px}
        .hero-highlight,.review-box,.step-card{border-radius:22px;border:1px solid #d7e3fb;background:#fff;box-shadow:0 8px 24px rgba(17,85,204,0.08)}
        .hero-highlight{padding:12px 14px;color:#2f5fb4;font-size:.95rem;font-weight:700}
        .hero-highlight--courses{text-align:left}
        .hero-highlight strong{display:block;color:var(--cor-principal);font-size:1.15rem;margin-bottom:4px}
        .benefits-slider{display:grid;gap:12px;margin-top:8px}
        .benefits-viewport{position:relative;min-height:76px;overflow:hidden}
        .benefit-slide{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:10px 12px;border-radius:16px;background:var(--cor-clara);color:var(--cor-principal);font-size:.98rem;font-weight:800;line-height:1.45;text-align:center;opacity:0;transform:translateX(18px);transition:opacity .28s ease,transform .28s ease;pointer-events:none}
        .benefit-slide.ativo{opacity:1;transform:translateX(0);pointer-events:auto}
        .benefits-controls{display:flex;align-items:center;justify-content:center;gap:10px}
        .benefits-nav{min-width:44px;min-height:44px;border:none;border-radius:999px;background:#fff;color:var(--cor-principal);box-shadow:0 6px 16px rgba(17,85,204,0.14);font:inherit;font-size:1.1rem;font-weight:900;cursor:pointer}
        .benefits-dots{display:flex;gap:6px;align-items:center;justify-content:center}
        .benefits-dot{width:9px;height:9px;border-radius:999px;background:#b7cbf4;transition:transform .2s ease,background .2s ease}
        .benefits-dot.ativo{background:var(--cor-principal);transform:scale(1.2)}
        .step-card{padding:18px 16px;width:100%;margin:0 auto;text-align:center}
        .step-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 12px;margin-top:10px;align-items:start;justify-content:center}
        .step-grid.step-grid--stacked{grid-template-columns:minmax(0,1fr);max-width:540px;margin-left:auto;margin-right:auto}
        .wizard-panel[data-step="dados"] .form-group,.wizard-panel[data-step="escolher"] .form-group{align-items:stretch;text-align:left}
        .wizard-panel[data-step="dados"] .form-group label,.wizard-panel[data-step="escolher"] .form-group label{width:100%;text-align:left}
        .wizard-panel[data-step="escolher"] .step-grid.step-grid--stacked{max-width:470px}
        .wizard-panel[data-step="escolher"] .form-group,.wizard-panel[data-step="escolher"] .form-group.full{width:100%;max-width:100%}
        .wizard-panel[data-step="escolher"] .input-with-action{width:100%;max-width:100%}
        .form-group{display:flex;flex-direction:column;gap:4px;width:100%;align-self:start;align-items:center;text-align:center}
        .form-group.full{grid-column:1 / -1}
        .form-group label,.review-title{color:var(--cor-principal);font-size:1rem;font-weight:800}
        .form-group input,.form-group select,.form-group textarea{display:block;width:100%!important;max-width:100%!important;min-width:0!important;margin:0!important;box-sizing:border-box;min-height:38px;height:38px;padding:7px 10px;border:1.2px solid var(--cor-borda);border-radius:10px;background:#f5f9ff;color:var(--cor-texto);font:inherit;line-height:1.2;text-align:left;outline:none;transition:border-color .2s ease,box-shadow .2s ease,background .2s ease}
        .form-group select{appearance:none;-webkit-appearance:none;-moz-appearance:none;background-image:url('data:image/svg+xml;utf8,<svg fill="%231155cc" height="20" viewBox="0 0 24 24" width="20" xmlns="http://www.w3.org/2000/svg"><path d="M7 10l5 5 5-5z"/></svg>');background-repeat:no-repeat;background-position:right 14px center;background-size:20px 20px;padding-right:44px}
        .form-group textarea{min-height:60px;height:auto;resize:vertical}
        .form-group input:focus,.form-group select:focus,.form-group textarea:focus{border-color:var(--cor-principal);background:#fff;box-shadow:0 0 0 4px rgba(17,85,204,0.12)}
        .readonly-field{background:#eef4ff!important;color:#2f5fb4!important;font-weight:700}
        .input-with-action{display:grid;grid-template-columns:minmax(0,1fr);gap:10px;align-items:stretch;justify-content:stretch}
        .input-with-action input{width:100%!important}
        .icon-button,.cta-button,.secondary-button,.submit-button{border:none;border-radius:18px;font:inherit;font-weight:800;cursor:pointer;transition:transform .16s ease,box-shadow .16s ease,background .16s ease,color .16s ease}
        .icon-button{min-width:56px;min-height:52px;background:var(--cor-principal);color:#fff;box-shadow:0 8px 16px rgba(17,85,204,0.22)}
        .wizard-panel[data-step="escolher"] .icon-button{width:100%!important;min-width:0!important;max-width:100%!important;height:38px!important;min-height:38px!important;padding:0;border-radius:10px;box-shadow:none}
        .panel-actions .cta-button,.panel-actions .secondary-button,.panel-actions .submit-button{width:100%!important;max-width:100%!important;min-width:0!important;margin:0!important;height:38px;font-size:1rem}
        .cta-button,.submit-button{background:linear-gradient(90deg,#1155cc 0%,#4f86ea 100%);color:#fff;box-shadow:0 10px 24px rgba(17,85,204,0.24)}
        .secondary-button{background:#fff;color:var(--cor-principal);border:2px solid var(--cor-principal)}
        .cta-button,.secondary-button,.submit-button{min-height:54px;padding:14px 22px;text-transform:uppercase;letter-spacing:.04em}
        .cta-button:hover,.secondary-button:hover,.submit-button:hover,.icon-button:hover{transform:translateY(-1px)}
        .panel-actions{display:flex;flex-direction:column-reverse;align-items:center;gap:12px;justify-content:space-between;margin-top:28px;max-width:420px;margin-left:auto;margin-right:auto}
        .panel-actions>*{flex:1}
        .balao-erro{margin-top:4px;padding:10px 14px;border-radius:14px;border:1px solid #0d47a1;background:#1155cc;color:#fff;font-size:.92rem;font-weight:700;line-height:1.35}
        .balao-erro[hidden]{display:none}
        .erro-campo{border-color:#1155cc!important;box-shadow:0 0 0 4px rgba(17,85,204,0.12)!important}
        .review-layout{display:grid;grid-template-columns:1fr;gap:8px;margin-top:10px;max-width:540px;margin-left:auto;margin-right:auto}
        .review-box{padding:10px;text-align:center}
        .review-box.full{grid-column:1 / -1}
        .review-list{display:grid;gap:6px;margin-top:8px;text-align:left}
        .review-item{display:grid;grid-template-columns:auto 1fr;align-items:center;column-gap:8px;padding:7px 9px;border-radius:10px;background:var(--cor-clara);text-align:left}
        .review-item strong{color:var(--cor-principal);font-size:.88rem;white-space:nowrap}
        .review-item strong::after{content:':'}
        .review-item span{color:var(--cor-texto);font-size:.94rem;word-break:break-word;text-align:left}
        .review-check{display:flex;gap:12px;align-items:flex-start;justify-content:flex-start;padding:10px 12px;border-radius:14px;background:var(--cor-clara);color:#17386d;line-height:1.45;text-align:left}
        .review-check input{margin-top:3px;width:20px;min-width:20px;height:20px;flex:0 0 20px;accent-color:var(--cor-principal)}
        .review-check span{flex:1 1 auto;min-width:0}
        .review-check ul{margin:8px 0 0 18px;padding:0;list-style-position:outside;text-align:left}
        .review-box .form-group{align-items:stretch;text-align:left}
        .review-box .form-group label{width:100%;text-align:left}
        @media(max-width:860px){.hero-grid,.review-layout{grid-template-columns:1fr}.step-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.step-grid.step-grid--stacked{grid-template-columns:minmax(0,1fr);max-width:540px}}
        @media(max-width:640px){
            html,body{width:100%!important;max-width:100%!important;overflow-x:hidden!important}body *{min-width:0}body{overflow-x:hidden}
            .main-header{padding:10px 12px}.header-logos{display:flex;flex-direction:column;align-items:center;gap:10px}.header-logos img,.logo,.logo-prefeitura-topo{max-width:min(88vw,280px);height:auto}
            .wizard-page{width:calc(100% - 8px)!important;max-width:100%!important;padding:4px 0 10px}.wizard-progress,.wizard-panel{width:100%!important;max-width:100%!important;padding:8px}.wizard-labels{grid-template-columns:1fr;gap:6px}
            .hero-card,.step-card,.review-box{width:100%!important;max-width:100%!important;padding:8px}.input-with-action{grid-template-columns:minmax(0,1fr);width:100%!important;max-width:100%!important}.panel-actions>*{width:100%}
            .step-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.step-grid.step-grid--stacked{grid-template-columns:minmax(0,1fr);max-width:100%}.review-layout{grid-template-columns:1fr;max-width:100%;gap:10px}
            .review-item,.form-group,.form-group input,.form-group select,.form-group textarea,.wizard-shell,.panel-actions,.review-check,.balao-erro{width:100%!important;max-width:100%!important}
            img,svg{max-width:100%!important;height:auto!important}
            .form-group input,.form-group select,.form-group textarea,.icon-button{min-height:32px;height:32px;font-size:.98em}.form-group textarea{min-height:60px;height:auto}
            .review-check{flex-direction:row;align-items:flex-start;padding:8px}.review-check input{width:22px;min-width:22px;height:22px;flex-basis:22px}.review-check ul{padding-left:2px}
            .hero-title,.panel-title{font-size:1.3rem}.hero-subtitle,.panel-subtitle{font-size:.92rem}.wizard-shell{border-radius:16px}.form-group.full{grid-column:auto}
        }
    </style>
</head>
<body data-start-step="{{ current_step }}">
    <noscript><img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id=2008632536670997&ev=PageView&noscript=1"/></noscript>
    <script src="/static/assistant.js"></script>
    <header class="main-header">
        <div class="header-logos">
            <img src="/static/logo-prefeitura.png" alt="Prefeitura do Rio" class="logo-prefeitura-topo">
        </div>
    </header>
    <div class="wizard-page">
        <div class="wizard-progress">
            <div class="wizard-track"><div class="wizard-fill" id="wizard-fill"></div></div>
            <div class="wizard-labels">
                <div class="wizard-label" data-step-label="index">1. In&#237;cio</div>
                <div class="wizard-label" data-step-label="dados">2. Dados pessoais</div>
                <div class="wizard-label" data-step-label="escolher">3. Escolher</div>
                <div class="wizard-label" data-step-label="revisao">4. Revis&#227;o</div>
            </div>
        </div>
        <div class="wizard-shell">
            <form id="wizard-form" method="POST" action="{{ url_for('inscricao_unica') }}" autocomplete="off" novalidate>
                <section class="wizard-panel" data-step="index">
                    <div class="hero-grid"><div class="hero-card">
                        <span class="hero-pill">MOVIMENTA RIO - CRISTIANE</span>
                        <h1 class="hero-title">CURSOS GRATUITOS EM SENADOR CAMA&#193;</h1>
                        <p class="hero-subtitle">Programa Movimenta Rio &#8226; Prefeitura do Rio de Janeiro</p>
                        <div class="hero-highlights">
                            <div class="hero-highlight hero-highlight--courses">
                                <strong>CURSOS DISPON&#205;VEIS:</strong>
                                &#128218; ATENDENTE DE SAL&#195;O DE CAF&#201; DA MANH&#195;<br>
                                &#128218; ORIENTADOR DE HOTELARIA<br>
                                &#128194; AUXILIAR ADMINISTRATIVO<br>
                                &#128218; SOCIAL MEDIA<br>
                                &#128241; MARKETING DIGITAL
                            </div>
                            <div class="hero-highlight">
                                <strong>BENEF&#205;CIOS</strong>
                                <div class="benefits-slider" data-benefits-slider>
                                    <div class="benefits-viewport">
                                        <div class="benefit-slide ativo">100% Gratuito</div>
                                        <div class="benefit-slide">Certificado de Conclus&#227;o</div>
                                        <div class="benefit-slide">Material Did&#225;tico Incluso</div>
                                    </div>
                                    <div class="benefits-controls">
                                        <button type="button" class="benefits-nav" data-benefits-prev aria-label="Anterior">&#8249;</button>
                                        <div class="benefits-dots" data-benefits-dots></div>
                                        <button type="button" class="benefits-nav" data-benefits-next aria-label="Pr&#243;ximo">&#8250;</button>
                                    </div>
                                </div>
                            </div>
                            <div class="hero-highlight">
                                <strong>MOVIMENTA RIO</strong>
                                Qualifica&#231;&#227;o profissional gratuita para ampliar suas oportunidades e fortalecer sua entrada no mercado de trabalho.
                            </div>
                        </div>
                        <div class="panel-actions">
                            <button type="button" class="cta-button" data-next="dados">Come&#231;ar inscri&#231;&#227;o</button>
                        </div>
                    </div></div>
                </section>
                <section class="wizard-panel" data-step="dados">
                    <div class="step-card">
                        <h2 class="panel-title">Dados pessoais</h2>
                        <div class="step-grid step-grid--stacked">
                            <div class="form-group full"><label for="nome">Nome completo *</label><input type="text" id="nome" name="nome" maxlength="50" placeholder="Digite seu nome completo" value="{{ form_data.get('nome', '') }}"><div class="balao-erro" id="nome-error" {% if not errors.get('nome') %}hidden{% endif %}>{{ errors.get('nome', '') }}</div></div>
                            <div class="form-group"><label for="genero">G&#234;nero *</label><select id="genero" name="genero"><option value="">Selecione</option>{% for genero in generos %}<option value="{{ genero }}" {% if form_data.get('genero') == genero %}selected{% endif %}>{{ genero }}</option>{% endfor %}</select><div class="balao-erro" id="genero-error" {% if not errors.get('genero') %}hidden{% endif %}>{{ errors.get('genero', '') }}</div></div>
                            <div class="form-group"><label for="cpf">CPF *</label><input type="text" id="cpf" name="cpf" maxlength="14" placeholder="000.000.000-00" value="{{ form_data.get('cpf', '') }}"><div class="balao-erro" id="cpf-error" {% if not errors.get('cpf') %}hidden{% endif %}>{{ errors.get('cpf', '') }}</div></div>
                            <div class="form-group"><label for="nascimento">Data de nascimento *</label><input type="text" id="nascimento" name="nascimento" maxlength="10" placeholder="dd/mm/aaaa" value="{{ form_data.get('nascimento', '') }}"><div class="balao-erro" id="nascimento-error" {% if not errors.get('nascimento') %}hidden{% endif %}>{{ errors.get('nascimento', '') }}</div></div>
                            <div class="form-group"><label for="whatsapp">WhatsApp *</label><input type="text" id="whatsapp" name="whatsapp" maxlength="16" placeholder="(00) 00000-0000" value="{{ form_data.get('whatsapp', '') }}"><div class="balao-erro" id="whatsapp-error" {% if not errors.get('whatsapp') %}hidden{% endif %}>{{ errors.get('whatsapp', '') }}</div></div>
                            <div class="form-group"><label for="cep">CEP *</label><input type="text" id="cep" name="cep" maxlength="9" placeholder="00000-000" value="{{ form_data.get('cep', '') }}"><div class="balao-erro" id="cep-error" {% if not errors.get('cep') %}hidden{% endif %}>{{ errors.get('cep', '') }}</div></div>
                            <div class="form-group"><label for="bairro">Bairro *</label><input type="text" id="bairro" name="bairro" maxlength="40" placeholder="Nome do bairro" value="{{ form_data.get('bairro', '') }}"><div class="balao-erro" id="bairro-error" {% if not errors.get('bairro') %}hidden{% endif %}>{{ errors.get('bairro', '') }}</div></div>
                            <div class="form-group full"><label for="email">E-mail *</label><input type="email" id="email" name="email" maxlength="60" placeholder="seuemail@gmail.com" value="{{ form_data.get('email', '') }}"><div class="balao-erro" id="email-error" {% if not errors.get('email') %}hidden{% endif %}>{{ errors.get('email', '') }}</div></div>
                        </div>
                        <div class="panel-actions">
                            <button type="button" class="secondary-button" data-prev="index">Voltar</button>
                            <button type="button" class="cta-button" data-next="escolher">Pr&#243;ximo</button>
                        </div>
                    </div>
                </section>
                <section class="wizard-panel" data-step="escolher">
                    <div class="step-card">
                        <h2 class="panel-title">Escolha seu curso</h2>
                        <div class="step-grid step-grid--stacked">
                            <div class="form-group">
                                <label for="local_id">Local</label>
                                <select id="local_id" name="local_id">{% for local_option in local_options %}<option value="{{ local_option.id }}" {% if form_data.get('local_id') == local_option.id %}selected{% endif %}>{{ local_option.nome }}</option>{% endfor %}</select>
                            </div>
                            <div class="form-group">
                                <label for="curso_id">Curso *</label>
                                <select id="curso_id" name="curso_id">
                                    <option value="" {% if not form_data.get('curso_id') %}selected{% endif %}>Selecione um curso</option>
                                    {% for course in course_catalog %}<option value="{{ course.id }}" {% if form_data.get('curso_id') == course.id %}selected{% endif %}>{{ course.nome }}</option>{% endfor %}
                                </select>
                                <div class="balao-erro" id="curso_id-error" {% if not errors.get('curso_id') %}hidden{% endif %}>{{ errors.get('curso_id', '') }}</div>
                            </div>
                            <div class="form-group full" style="display:none;">
                                <label for="opcao_id">Turma *</label>
                                <select id="opcao_id" name="opcao_id">
                                    <option value="" {% if not form_data.get('opcao_id') %}selected{% endif %}>Selecione uma turma</option>
                                    {% for option in course_options %}<option value="{{ option.id }}" {% if form_data.get('opcao_id') == option.id %}selected{% endif %}>{{ option.turma }}</option>{% endfor %}
                                </select>
                                <div class="balao-erro" id="opcao_id-error" {% if not errors.get('opcao_id') %}hidden{% endif %}>{{ errors.get('opcao_id', '') }}</div>
                            </div>
                            <input type="hidden" id="local" name="local" value="{{ form_data.get('local', '') }}">
                            <input type="hidden" id="curso" name="curso" value="{{ form_data.get('curso', '') }}">
                            <input type="hidden" id="turma" name="turma" value="{{ form_data.get('turma', '') }}">
                            <div class="form-group" id="dias-aula-group"><label for="dias_aula">DIA DE AULA</label><input type="text" id="dias_aula" name="dias_aula" class="readonly-field" readonly value="{{ form_data.get('dias_aula', '') }}"></div>
                            <div class="form-group" id="horario-group"><label for="horario">HOR&#193;RIO</label><input type="text" id="horario" name="horario" class="readonly-field" readonly value="{{ form_data.get('horario', '') }}"></div>
                            <div class="form-group" id="data-inicio-group"><label for="data_inicio">DATA DE IN&#205;CIO</label><input type="text" id="data_inicio" name="data_inicio" class="readonly-field" readonly value="{{ form_data.get('data_inicio', '') }}"></div>
                            <div class="form-group" id="encerramento-group"><label for="encerramento">ENCERRAMENTO</label><input type="text" id="encerramento" name="encerramento" class="readonly-field" readonly value="{{ form_data.get('encerramento', '') }}"></div>
                            <div class="form-group full" id="endereco-group"><label for="endereco_curso">ENDERE&#199;O</label><div class="input-with-action"><input type="text" id="endereco_curso" name="endereco_curso" class="readonly-field" readonly value="{{ form_data.get('endereco_curso', '') }}"><button type="button" class="icon-button" id="btn-copiar-endereco" title="Copiar">COPIAR &#128203;</button></div></div>
                        </div>
                        <div class="panel-actions">
                            <button type="button" class="secondary-button" data-prev="dados">Voltar</button>
                            <button type="button" class="cta-button" data-next="revisao">Ir para revis&#227;o</button>
                        </div>
                    </div>
                </section>
                <section class="wizard-panel" data-step="revisao">
                    <div class="step-card">
                        <h2 class="panel-title">Revise antes de finalizar</h2>
                        <p class="panel-subtitle">Confira os dados preenchidos e confirme sua participa&#231;&#227;o.</p>
                        <div class="review-layout">
                            <div class="review-box"><div class="review-title">Dados pessoais</div><div class="review-list">
                                <div class="review-item"><strong>Nome</strong><span data-review="nome"></span></div>
                                <div class="review-item"><strong>CPF</strong><span data-review="cpf"></span></div>
                                <div class="review-item"><strong>Nascimento</strong><span data-review="nascimento"></span></div>
                                <div class="review-item"><strong>G&#234;nero</strong><span data-review="genero"></span></div>
                                <div class="review-item"><strong>WhatsApp</strong><span data-review="whatsapp"></span></div>
                                <div class="review-item"><strong>CEP</strong><span data-review="cep"></span></div>
                                <div class="review-item"><strong>Bairro</strong><span data-review="bairro"></span></div>
                                <div class="review-item"><strong>E-mail</strong><span data-review="email"></span></div>
                            </div></div>
                            <div class="review-box"><div class="review-title">Informa&#231;&#245;es do curso</div><div class="review-list">
                                <div class="review-item"><strong>Local</strong><span data-review="local"></span></div>
                                <div class="review-item"><strong>Curso</strong><span data-review="curso"></span></div>
                                <div class="review-item"><strong>Turma</strong><span data-review="turma"></span></div>
                                <div class="review-item"><strong>Dia</strong><span data-review="dias_aula"></span></div>
                                <div class="review-item"><strong>Hor&#225;rio</strong><span data-review="horario"></span></div>
                                <div class="review-item"><strong>In&#237;cio</strong><span data-review="data_inicio"></span></div>
                                <div class="review-item"><strong>Encerramento</strong><span data-review="encerramento"></span></div>
                                <div class="review-item"><strong>Endere&#231;o</strong><span data-review="endereco_curso"></span></div>
                            </div></div>
                            <div class="review-box full"><div class="form-group"><label for="como_conheceu">Como conheceu (opcional)</label><input type="text" id="como_conheceu" name="como_conheceu" maxlength="120" placeholder="Digite como conheceu o projeto" value="{{ form_data.get('como_conheceu', '') }}"></div></div>
                            <div class="review-box full">
                                <div style="margin-bottom:10px;color:#2f5fb4;font-size:.98rem;text-align:left;"><strong>Elegibilidade:</strong> Este curso &#233; destinado a pessoas com 16 anos ou mais interessadas em qualifica&#231;&#227;o profissional.</div>
                                <label class="review-check" for="confirma_dados">
                                    <input type="checkbox" id="confirma_dados" name="confirma_dados" value="sim" {% if form_data.get('confirma_dados') %}checked{% endif %}>
                                    <span>Confirmo que tenho 16 anos ou mais e interesse em participar do curso selecionado.<br>Todas as informa&#231;&#245;es fornecidas s&#227;o verdadeiras e estou de acordo com os termos de participa&#231;&#227;o.<br>Autorizo o uso dos meus dados para fins de inscri&#231;&#227;o e contato relacionado ao curso.<br>Tamb&#233;m autorizo o uso da minha imagem para divulga&#231;&#227;o nos canais de comunica&#231;&#227;o e redes sociais do projeto e da Prefeitura do Rio de Janeiro.</span>
                                </label>
                                <div style="margin-top:10px;"><strong>Ao confirmar voc&#234; declara a ci&#234;ncia de que:</strong><ul><li>O curso &#233; totalmente gratuito</li><li>Os dados ser&#227;o usados apenas para inscri&#231;&#227;o</li></ul></div>
                                <div class="balao-erro" id="confirma_dados-error" {% if not errors.get('confirma_dados') %}hidden{% endif %}>{{ errors.get('confirma_dados', '') }}</div>
                            </div>
                        </div>
                        <div class="panel-actions">
                            <button type="button" class="secondary-button" data-prev="escolher">Voltar</button>
                            <button type="submit" class="submit-button">Finalizar inscri&#231;&#227;o</button>
                        </div>
                    </div>
                </section>
            </form>
        </div>
    </div>
    <script>
    document.addEventListener('DOMContentLoaded', function () {
        const stepOrder=['index','dados','escolher','revisao'];
        const progressByStep={index:25,dados:45,escolher:70,revisao:90};
        const form=document.getElementById('wizard-form');
        const fill=document.getElementById('wizard-fill');
        const startStep=document.body.dataset.startStep||'index';
        const panels=Array.from(document.querySelectorAll('[data-step]'));
        const labels=Array.from(document.querySelectorAll('[data-step-label]'));
        const reviewTargets=Array.from(document.querySelectorAll('[data-review]'));
        const benefitsSliders=Array.from(document.querySelectorAll('[data-benefits-slider]'));
        const localOptions={{ local_options|tojson }};
        const courseCatalog={{ course_catalog|tojson }};
        const courseOptions={{ course_options|tojson }};
        const localOptionsById=Object.fromEntries(localOptions.map(o=>[String(o.id),o]));
        const courseCatalogById=Object.fromEntries(courseCatalog.map(o=>[String(o.id),o]));
        const courseOptionsById=Object.fromEntries(courseOptions.map(o=>[String(o.id),o]));
        const nomeInput=document.getElementById('nome'),generoInput=document.getElementById('genero'),cpfInput=document.getElementById('cpf'),nascimentoInput=document.getElementById('nascimento'),whatsappInput=document.getElementById('whatsapp'),cepInput=document.getElementById('cep'),bairroInput=document.getElementById('bairro'),emailInput=document.getElementById('email');
        const localSelect=document.getElementById('local_id'),courseSelect=document.getElementById('curso_id'),optionInput=document.getElementById('opcao_id');
        const localInput=document.getElementById('local'),cursoInput=document.getElementById('curso'),turmaInput=document.getElementById('turma');
        const diasAulaInput=document.getElementById('dias_aula'),horarioInput=document.getElementById('horario'),dataInicioInput=document.getElementById('data_inicio'),encerramentoInput=document.getElementById('encerramento'),enderecoInput=document.getElementById('endereco_curso');
        const confirmaDadosInput=document.getElementById('confirma_dados'),btnCopiarEndereco=document.getElementById('btn-copiar-endereco');
        const diasAulaGroup=document.getElementById('dias-aula-group'),horarioGroup=document.getElementById('horario-group'),dataInicioGroup=document.getElementById('data-inicio-group'),encerramentoGroup=document.getElementById('encerramento-group'),enderecoGroup=document.getElementById('endereco-group');
        function somenteDigitos(v){return(v||'').replace(/\D/g,'');}
        function setError(id,msg){const f=document.getElementById(id),e=document.getElementById(id+'-error');if(f)f.classList.toggle('erro-campo',Boolean(msg));if(e){e.textContent=msg||'';e.hidden=!msg;}}
        function isEAD(op){return !op||(!op.dias_aula&&!op.horario&&!op.data_inicio);}
        function mostrarCamposInfo(det){if(diasAulaGroup)diasAulaGroup.style.display=det?'':'none';if(horarioGroup)horarioGroup.style.display=det?'':'none';if(dataInicioGroup)dataInicioGroup.style.display=det?'':'none';if(encerramentoGroup)encerramentoGroup.style.display=det?'':'none';if(enderecoGroup)enderecoGroup.style.display=det?'':'none';}
        function initBenefitsSlider(slider){const slides=Array.from(slider.querySelectorAll('.benefit-slide')),dotsHost=slider.querySelector('[data-benefits-dots]'),prevBtn=slider.querySelector('[data-benefits-prev]'),nextBtn=slider.querySelector('[data-benefits-next]');if(!slides.length||!dotsHost||!prevBtn||!nextBtn)return;let cur=Math.max(0,slides.findIndex(s=>s.classList.contains('ativo'))),tid;const dots=slides.map((_,i)=>{const d=document.createElement('button');d.type='button';d.className='benefits-dot';d.setAttribute('aria-label','Benef\u00edcio '+(i+1));d.addEventListener('click',()=>{show(i);restart();});dotsHost.appendChild(d);return d;});function show(i){cur=(i+slides.length)%slides.length;slides.forEach((s,si)=>s.classList.toggle('ativo',si===cur));dots.forEach((d,di)=>d.classList.toggle('ativo',di===cur));}function restart(){clearInterval(tid);tid=setInterval(()=>show(cur+1),3200);}prevBtn.addEventListener('click',()=>{show(cur-1);restart();});nextBtn.addEventListener('click',()=>{show(cur+1);restart();});slider.addEventListener('mouseenter',()=>clearInterval(tid));slider.addEventListener('mouseleave',restart);show(cur);restart();}
        function mostrarPasso(step){panels.forEach(p=>p.classList.toggle('ativo',p.dataset.step===step));labels.forEach(l=>l.classList.toggle('ativo',l.dataset.stepLabel===step));fill.style.width=(progressByStep[step]||25)+'%';window.scrollTo({top:0,behavior:'smooth'});}
        function syncReview(){reviewTargets.forEach(function(t){const f=document.getElementById(t.dataset.review);if(!f){t.textContent='';return;}if(f.tagName==='SELECT'){const s=f.options[f.selectedIndex];t.textContent=s?s.text.trim():'';return;}t.textContent=f.value.trim();});}
        function mascaraCPF(){let v=somenteDigitos(cpfInput.value).slice(0,11);if(v.length>9)v=v.replace(/(\d{3})(\d{3})(\d{3})(\d{1,2})/,'$1.$2.$3-$4');else if(v.length>6)v=v.replace(/(\d{3})(\d{3})(\d{1,3})/,'$1.$2.$3');else if(v.length>3)v=v.replace(/(\d{3})(\d{1,3})/,'$1.$2');cpfInput.value=v;}
        function mascaraNascimento(){let v=somenteDigitos(nascimentoInput.value).slice(0,8);if(v.length>4)v=v.replace(/(\d{2})(\d{2})(\d{1,4})/,'$1/$2/$3');else if(v.length>2)v=v.replace(/(\d{2})(\d{1,2})/,'$1/$2');nascimentoInput.value=v;}
        function mascaraWhatsapp(){let v=somenteDigitos(whatsappInput.value).slice(0,11);if(v.length>6)v=v.replace(/(\d{2})(\d{5})(\d{0,4})/,'($1) $2-$3');else if(v.length>2)v=v.replace(/(\d{2})(\d{1,5})/,'($1) $2');whatsappInput.value=v;}
        function mascaraCep(){let v=somenteDigitos(cepInput.value).slice(0,8);if(v.length>5)v=v.replace(/(\d{5})(\d{1,3})/,'$1-$2');cepInput.value=v;}
        function validarCPF(cpf){const d=somenteDigitos(cpf);if(d.length!==11||/^(\d)\1+$/.test(d))return false;let s=0;for(let i=0;i<9;i++)s+=Number(d[i])*(10-i);let dv=(s*10)%11;if(dv===10)dv=0;if(dv!==Number(d[9]))return false;s=0;for(let i=0;i<10;i++)s+=Number(d[i])*(11-i);dv=(s*10)%11;if(dv===10)dv=0;return dv===Number(d[10]);}
        function validarEmail(e){return/^[a-zA-Z0-9_.+-]+@((gmail|hotmail|outlook|yahoo)\.(com|com\.br))$/i.test((e||'').trim());}
        function idadePermitida(v){const p=(v||'').split('/');if(p.length!==3)return false;const dt=new Date(Number(p[2]),Number(p[1])-1,Number(p[0]));if(isNaN(dt)||dt.getDate()!==Number(p[0]))return false;const hoje=new Date();let idade=hoje.getFullYear()-dt.getFullYear();if(hoje.getMonth()<dt.getMonth()||(hoje.getMonth()===dt.getMonth()&&hoje.getDate()<dt.getDate()))idade--;return idade>=16&&idade<=90;}
        function validarDDD(w){const d=somenteDigitos(w);if(d.length<11)return false;return['11','12','13','14','15','16','17','18','19','21','22','24','27','28','31','32','33','34','35','37','38','41','42','43','44','45','46','47','48','49','51','53','54','55','61','62','63','64','65','66','67','68','69','71','73','74','75','77','79','81','82','83','84','85','86','87','88','89','91','92','93','94','95','96','97','98','99'].includes(d.slice(0,2));}
        function validarNome(){const v=nomeInput.value.trim();if(!v){setError('nome','Digite seu nome completo.');return false;}if(v.length>50){setError('nome','O nome deve ter no m\u00e1ximo 50 caracteres.');return false;}if(!/^[A-Za-z\u00C0-\u00FF '\u00b4`^~.-]+$/.test(v)){setError('nome','Use apenas letras e sinais permitidos no nome.');return false;}setError('nome','');return true;}
        function validarGenero(){if(!generoInput.value){setError('genero','Selecione o g\u00eanero.');return false;}setError('genero','');return true;}
        function validarCampoCPF(){if(!validarCPF(cpfInput.value)){setError('cpf','CPF inv\u00e1lido. Verifique e digite novamente.');return false;}setError('cpf','');return true;}
        function validarNascimento(){if(!idadePermitida(nascimentoInput.value)){setError('nascimento','Idade permitida: de 16 at\u00e9 90 anos.');return false;}setError('nascimento','');return true;}
        function validarWhatsapp(){const d=somenteDigitos(whatsappInput.value);if(d.length!==11||!/^\(\d{2}\) \d{5}-\d{4}$/.test(whatsappInput.value)||!validarDDD(whatsappInput.value)){setError('whatsapp','Informe um WhatsApp com DDD v\u00e1lido do Brasil.');return false;}setError('whatsapp','');return true;}
        function validarCampoCep(){if(!/^\d{5}-\d{3}$/.test((cepInput.value||'').trim())){setError('cep','CEP inv\u00e1lido. Formato: 00000-000.');return false;}setError('cep','');return true;}
        function validarBairro(){const v=bairroInput.value.trim();if(!v){setError('bairro','Informe o bairro.');return false;}if(v.length>40){setError('bairro','O bairro deve ter no m\u00e1ximo 40 caracteres.');return false;}setError('bairro','');return true;}
        function validarCampoEmail(){if(!validarEmail(emailInput.value)){setError('email','Digite um e-mail v\u00e1lido do Gmail, Hotmail, Outlook ou Yahoo.');return false;}setError('email','');return true;}
        function validarPassoDados(){const checks=[{ok:validarNome(),field:nomeInput},{ok:validarGenero(),field:generoInput},{ok:validarCampoCPF(),field:cpfInput},{ok:validarNascimento(),field:nascimentoInput},{ok:validarWhatsapp(),field:whatsappInput},{ok:validarCampoCep(),field:cepInput},{ok:validarBairro(),field:bairroInput},{ok:validarCampoEmail(),field:emailInput}];const first=checks.find(c=>!c.ok);if(first){first.field.focus();return false;}return true;}
        function validarPassoEscolher(){if(!courseCatalogById[String(courseSelect.value)]){setError('curso_id','Selecione um curso v\u00e1lido.');courseSelect.focus();return false;}setError('curso_id','');if(!courseOptionsById[String(optionInput.value)]){setError('opcao_id','Selecione uma turma v\u00e1lida.');optionInput.focus();return false;}setError('opcao_id','');return true;}
        function validarPassoRevisao(){if(!confirmaDadosInput.checked){setError('confirma_dados','Confirme os dados para finalizar a inscri\u00e7\u00e3o.');confirmaDadosInput.focus();return false;}setError('confirma_dados','');return true;}
        function setSelectOptions(select,items,placeholder,selectedValue,labelKey){const cur=String(selectedValue||'');select.innerHTML='';const ph=document.createElement('option');ph.value='';ph.textContent=placeholder;ph.selected=!cur;select.appendChild(ph);items.forEach(function(item){const opt=document.createElement('option');opt.value=String(item.id);opt.textContent=item[labelKey];opt.selected=opt.value===cur;select.appendChild(opt);});}
        function getCoursesForLocal(localId){return courseCatalog.filter(c=>String(c.local_id)===String(localId||''));}
        function getTurmasForCourse(courseId){return courseOptions.filter(o=>String(o.curso_id)===String(courseId||''));}
        function limparDetalhesCurso(){turmaInput.value='';diasAulaInput.value='';horarioInput.value='';dataInicioInput.value='';encerramentoInput.value='';enderecoInput.value='';}
        function aplicarLocal(localId){const s=localOptionsById[String(localId||'')];localInput.value=s?s.nome:'';}
        function aplicarCurso(courseId){const s=courseCatalogById[String(courseId||'')];cursoInput.value=s?s.nome:'';}
        function aplicarOpcaoCurso(optionId){const opt=courseOptionsById[String(optionId)];if(!opt){turmaInput.value='';limparDetalhesCurso();mostrarCamposInfo(false);return;}localSelect.value=String(opt.local_id);courseSelect.value=String(opt.curso_id);localInput.value=opt.local;optionInput.value=String(opt.id);cursoInput.value=opt.curso;turmaInput.value=opt.turma;diasAulaInput.value=opt.dias_aula;horarioInput.value=opt.horario;dataInicioInput.value=opt.data_inicio;encerramentoInput.value=opt.encerramento;enderecoInput.value=opt.endereco_curso;setError('curso_id','');setError('opcao_id','');mostrarCamposInfo(!isEAD(opt));syncReview();}
        function atualizarCursos(selectedCourseId){const cursos=getCoursesForLocal(localSelect.value);setSelectOptions(courseSelect,cursos,'Selecione um curso',selectedCourseId,'nome');aplicarLocal(localSelect.value);aplicarCurso(courseSelect.value);}
        function atualizarTurmas(selectedOptionId){const turmas=getTurmasForCourse(courseSelect.value);setSelectOptions(optionInput,turmas,'Selecione uma turma',selectedOptionId,'turma');aplicarCurso(courseSelect.value);if(turmas.length===1&&!selectedOptionId){aplicarOpcaoCurso(String(turmas[0].id));}}
        async function buscarBairroPorCep(){const cepLimpo=somenteDigitos(cepInput.value);if(cepLimpo.length!==8)return;try{const res=await fetch('https://viacep.com.br/ws/'+cepLimpo+'/json/');const data=await res.json();if(!data.erro&&data.bairro){bairroInput.value=data.bairro;validarBairro();syncReview();}}catch(e){console.error(e);}}
        document.querySelectorAll('[data-next]').forEach(function(btn){btn.addEventListener('click',function(){const target=btn.dataset.next;if(target==='escolher'&&!validarPassoDados())return;if(target==='revisao'&&!validarPassoEscolher())return;syncReview();mostrarPasso(target);});});
        document.querySelectorAll('[data-prev]').forEach(function(btn){btn.addEventListener('click',function(){syncReview();mostrarPasso(btn.dataset.prev);});});
        form.addEventListener('submit',function(e){if(!validarPassoDados()){e.preventDefault();mostrarPasso('dados');return;}syncReview();if(!validarPassoRevisao()){e.preventDefault();mostrarPasso('revisao');}});
        nomeInput.addEventListener('blur',validarNome);generoInput.addEventListener('change',validarGenero);
        cpfInput.addEventListener('input',function(){mascaraCPF();if(somenteDigitos(cpfInput.value).length===11)validarCampoCPF();else setError('cpf','');syncReview();});
        nascimentoInput.addEventListener('input',function(){mascaraNascimento();syncReview();});nascimentoInput.addEventListener('blur',validarNascimento);
        whatsappInput.addEventListener('input',function(){mascaraWhatsapp();if(somenteDigitos(whatsappInput.value).length>=10)validarWhatsapp();else setError('whatsapp','');syncReview();});
        cepInput.addEventListener('input',function(){mascaraCep();bairroInput.value='';if(cepInput.value.length===9){validarCampoCep();buscarBairroPorCep();}else setError('cep','');syncReview();});
        bairroInput.addEventListener('blur',function(){validarBairro();syncReview();});
        emailInput.addEventListener('input',function(){if(emailInput.value.trim())validarCampoEmail();else setError('email','');syncReview();});
        localSelect.addEventListener('change',function(){atualizarCursos('');atualizarTurmas('');optionInput.value='';cursoInput.value='';limparDetalhesCurso();mostrarCamposInfo(false);syncReview();});
        courseSelect.addEventListener('change',function(){atualizarTurmas('');optionInput.value='';aplicarCurso(courseSelect.value);limparDetalhesCurso();mostrarCamposInfo(false);setError('curso_id','');syncReview();});
        optionInput.addEventListener('change',function(){aplicarOpcaoCurso(optionInput.value);syncReview();});
        confirmaDadosInput.addEventListener('change',function(){if(confirmaDadosInput.checked)setError('confirma_dados','');});
        ['nome','genero','whatsapp','cep','bairro','email','local_id','curso_id','opcao_id','local','curso','turma','dias_aula','horario','data_inicio','encerramento','endereco_curso','como_conheceu'].forEach(function(id){const f=document.getElementById(id);if(!f)return;f.addEventListener('input',syncReview);f.addEventListener('change',syncReview);});
        if(btnCopiarEndereco&&enderecoInput){btnCopiarEndereco.addEventListener('click',async function(){try{await navigator.clipboard.writeText(enderecoInput.value);}catch{enderecoInput.select();document.execCommand('copy');}btnCopiarEndereco.textContent='COPIADO \u2705';setTimeout(()=>{btnCopiarEndereco.textContent='COPIAR &#128203;';},1200);});}
        mostrarCamposInfo(false);
        atualizarCursos(courseSelect.value);atualizarTurmas(optionInput.value);aplicarLocal(localSelect.value);aplicarCurso(courseSelect.value);aplicarOpcaoCurso(optionInput.value);benefitsSliders.forEach(initBenefitsSlider);syncReview();mostrarPasso(stepOrder.includes(startStep)?startStep:'index');
    });
    </script>
</body>
</html>
'''
TEMPLATE_CONFIRMACAO = r'''
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Movimenta Rio - Cristiane</title>
    <link rel="stylesheet" href="/static/style.css">
    <link rel="stylesheet" href="/static/assistant.css">
    <link href="https://fonts.googleapis.com/css2?family=Wise:wght@400;700;900&display=swap" rel="stylesheet">
    <script>
        !function(f,b,e,v,n,t,s)
        {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
        n.callMethod.apply(n,arguments):n.queue.push(arguments)};
        if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
        n.queue=[];t=b.createElement(e);t.async=!0;
        t.src=v;s=b.getElementsByTagName(e)[0];
        s.parentNode.insertBefore(t,s)}(window, document,'script',
        'https://connect.facebook.net/en_US/fbevents.js');
        fbq('init', '2008632536670997');
        fbq('track', 'PageView');
    </script>
    <style>
        :root{--cor-principal:#1155cc;--cor-clara:#eef4ff;--cor-texto:#17386d;--sombra-card:0 18px 55px rgba(17,85,204,0.18)}
        body{min-height:100vh;margin:0;background:radial-gradient(circle at top left,rgba(17,85,204,0.15),transparent 32%),linear-gradient(140deg,#f5f9ff 0%,#fff 55%,#dfeaff 100%);font-family:'Wise',Arial,sans-serif}
        .main-header{border-bottom:4px solid #1155cc;background:rgba(255,255,255,0.92)}
        .confirm-page{width:min(680px,calc(100% - 16px));margin:0 auto;padding:10px 0 20px;text-align:center}
        .wizard-progress{margin:12px auto 16px;padding:14px 14px 16px;border-radius:28px;background:rgba(255,255,255,0.9);box-shadow:0 12px 30px rgba(17,85,204,0.12)}
        .wizard-track{width:100%;height:14px;border-radius:999px;background:#dbe6fb;overflow:hidden}
        .wizard-fill{width:100%;height:100%;background:linear-gradient(90deg,#1155cc 0%,#4f86ea 100%);border-radius:999px}
        .wizard-labels{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}
        .wizard-label{padding:10px 8px;border:1px solid #c9daf8;border-radius:16px;background:#fff;color:#2f5fb4;font-size:.84rem;font-weight:700;text-align:center}
        .wizard-label.ativo{border-color:var(--cor-principal);background:var(--cor-clara);color:var(--cor-principal)}
        .confirm-shell{background:rgba(255,255,255,0.88);border:1px solid rgba(255,255,255,0.9);border-radius:30px;box-shadow:var(--sombra-card);overflow:hidden;text-align:center}
        .confirm-card{padding:20px 16px 18px;background:transparent;text-align:center;max-width:620px;margin:0 auto}
        .checkmark{width:120px;height:120px;margin:0 auto 12px}
        .checkmark svg{width:100%;height:100%;stroke:#1155cc;fill:none}
        .confirm-card h1{margin:0 0 10px;color:#1155cc;font-size:clamp(1.8rem,4vw,2.6rem);letter-spacing:-.04em}
        .protocol-box{margin:16px auto 12px;padding:14px;max-width:320px;border-radius:16px;background:#eef4ff;border:2px solid #1155cc}
        .protocol-box strong{display:block;color:#1155cc;font-size:.98rem;margin-bottom:8px;text-transform:uppercase;letter-spacing:.04em}
        .protocol-box span{display:block;color:#1155cc;font-size:1.35rem;font-weight:900;letter-spacing:.08em;word-break:break-all}
        .next-steps{margin:16px auto 0;max-width:460px;padding:14px;text-align:center;border-radius:18px;background:#fff;border:1px solid #d7e3fb}
        .next-steps h2{margin:0 0 12px;color:#1155cc;font-size:1.2rem}
        .next-steps ol{margin:0;padding-left:22px;color:#2f5fb4;line-height:1.55;list-style-position:inside}
        .actions{display:grid;grid-template-columns:1fr;gap:10px;margin-top:16px;max-width:380px;margin-left:auto;margin-right:auto}
        .action-button{display:flex;align-items:center;justify-content:center;min-height:42px;padding:10px 14px;border-radius:12px;text-decoration:none;text-transform:uppercase;font-weight:800;letter-spacing:.03em;text-align:center;transition:transform .16s ease,box-shadow .16s ease}
        .action-button.primary{background:linear-gradient(90deg,#1155cc 0%,#4f86ea 100%);color:#fff;box-shadow:0 10px 24px rgba(17,85,204,0.24)}
        .action-button.secondary{background:#fff;color:#1155cc;border:2px solid #1155cc}
        .action-button:hover{transform:translateY(-1px)}
        @media(max-width:640px){html,body{width:100%!important;max-width:100%!important;overflow-x:hidden!important}body *{min-width:0}.main-header{padding:10px 12px}.header-logos{display:flex;flex-direction:column;align-items:center;gap:10px}.header-logos img{max-width:min(88vw,280px);height:auto}.confirm-page{width:calc(100% - 8px)!important;max-width:100%!important;padding:6px 0 12px}.confirm-card{width:100%!important;max-width:100%!important;padding:14px 10px 12px}.wizard-progress{width:100%!important;max-width:100%!important;padding:10px;border-radius:18px}.wizard-labels{grid-template-columns:1fr;gap:6px}.confirm-shell{width:100%!important;max-width:100%!important;border-radius:18px}.protocol-box span{font-size:1.3rem}.next-steps,.actions,.action-button,.protocol-box,.wizard-label,.wizard-track{width:100%!important;max-width:100%!important}img,svg{max-width:100%!important;height:auto!important}}
    </style>
</head>
<body>
    <noscript><img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id=2008632536670997&ev=PageView&noscript=1"/></noscript>
    <script src="/static/assistant.js"></script>
    <header class="main-header"><div class="header-logos"><img src="/static/logo-prefeitura.png" alt="Prefeitura do Rio" class="logo-prefeitura-topo"></div></header>
    <div class="confirm-page">
        <div class="wizard-progress">
            <div class="wizard-track"><div class="wizard-fill"></div></div>
            <div class="wizard-labels">
                <div class="wizard-label">1. In&#237;cio</div>
                <div class="wizard-label">2. Dados pessoais</div>
                <div class="wizard-label">3. Escolher</div>
                <div class="wizard-label ativo">4. Confirma&#231;&#227;o</div>
            </div>
        </div>
        <div class="confirm-shell"><div class="confirm-card">
            <div class="checkmark"><svg viewBox="0 0 200 200"><circle cx="100" cy="100" r="90" stroke-width="16"></circle><polyline points="60,110 95,145 145,75" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"></polyline></svg></div>
            <h1>Inscri&#231;&#227;o realizada com sucesso</h1>
            <div class="protocol-box"><strong>N&#250;mero de protocolo</strong><span>{{ protocolo }}</span></div>
            <div class="actions">
                <a class="action-button primary" href="{{ whatsapp_share_url }}" target="_blank" rel="noopener noreferrer">Compartilhar no WhatsApp</a>
                <a class="action-button secondary" href="{{ url_for('home') }}">Voltar ao in&#237;cio</a>
            </div>
            <div class="next-steps"><h2>Pr&#243;ximos passos</h2><ol>
                <li>Aguarde nosso contato via WhatsApp.</li>
                <li>Prepare RG, CPF e comprovante de resid&#234;ncia.</li>
                <li>Fique atento ao contato com os detalhes do curso.</li>
                <li>Compare&#231;a ao local informado no dia marcado.</li>
            </ol></div>
        </div></div>
    </div>
</body>
</html>
'''
# ── FLASK APP ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "chave-secreta-para-sessao")
def get_default_form_data(source=None):
    form_data = {
        "nome":"","genero":"","cpf":"","nascimento":"","whatsapp":"",
        "cep":"","bairro":"","email":"",
        "local_id":"1","curso_id":"","opcao_id":"",
        "local":"MARCO 7 - SENADOR CAMA\u00c1 \u2014 SALA 1",
        "curso":"","turma":"","dias_aula":"","horario":"",
        "data_inicio":"","encerramento":"","endereco_curso":"",
        "como_conheceu":"","confirma_dados":"",
    }
    if source:
        for key in form_data:
            value = source.get(key, form_data[key])
            if key == "confirma_dados":
                form_data[key] = "sim" if value else ""
            else:
                form_data[key] = (value or "").strip()
        fill_form_data_from_selection(form_data)
    return form_data
def cpf_valido(cpf):
    digits = re.sub(r"\D","",cpf or "")
    if len(digits)!=11 or len(set(digits))==1: return False
    total = sum(int(digits[i])*(10-i) for i in range(9))
    d=(total*10)%11
    if d==10: d=0
    if d!=int(digits[9]): return False
    total = sum(int(digits[i])*(11-i) for i in range(10))
    d=(total*10)%11
    if d==10: d=0
    return d==int(digits[10])
def idade_aceita(nascimento):
    try: dn = datetime.strptime(nascimento,"%d/%m/%Y")
    except ValueError: return False
    hoje = datetime.today()
    idade = hoje.year - dn.year
    if (hoje.month,hoje.day)<(dn.month,dn.day): idade-=1
    return 16<=idade<=90
def whatsapp_valido(whatsapp):
    digits = re.sub(r"\D","",whatsapp or "")
    if len(digits)!=11: return False
    if not re.fullmatch(r"\(\d{2}\) \d{5}-\d{4}",whatsapp or ""): return False
    return digits[:2] in VALID_DDDS
def validate_form_data(form_data):
    errors = {}
    sel_local  = get_local_option(form_data["local_id"])
    sel_course = get_course_catalog_option(form_data["curso_id"])
    sel_option = get_course_option(form_data["opcao_id"])
    if not sel_local: errors["local_id"]="Selecione um local v\u00e1lido."
    if not sel_course or sel_course["local_id"]!=form_data["local_id"]:
        errors["curso_id"]="Selecione um curso v\u00e1lido."
    if not sel_option or sel_option["local_id"]!=form_data["local_id"] or sel_option["curso_id"]!=form_data["curso_id"]:
        errors["opcao_id"]="Selecione uma turma v\u00e1lida."
    nome = form_data["nome"]
    if not nome: errors["nome"]="Digite seu nome completo."
    elif len(nome)>50: errors["nome"]="O nome deve ter no m\u00e1ximo 50 caracteres."
    elif not NAME_PATTERN.fullmatch(nome): errors["nome"]="Use apenas letras e sinais permitidos no nome."
    if form_data["genero"] not in {"Feminino","Masculino","Outro","Prefiro n\u00e3o dizer"}:
        errors["genero"]="Selecione o g\u00eanero."
    if not cpf_valido(form_data["cpf"]): errors["cpf"]="CPF inv\u00e1lido. Verifique e digite novamente."
    if not idade_aceita(form_data["nascimento"]): errors["nascimento"]="Idade permitida: de 16 at\u00e9 90 anos."
    if not whatsapp_valido(form_data["whatsapp"]): errors["whatsapp"]="Informe um WhatsApp com DDD v\u00e1lido do Brasil."
    if not re.fullmatch(r"\d{5}-\d{3}",form_data["cep"] or ""): errors["cep"]="CEP inv\u00e1lido. Formato: 00000-000."
    bairro = form_data["bairro"]
    if not bairro: errors["bairro"]="Informe o bairro."
    elif len(bairro)>40: errors["bairro"]="O bairro deve ter no m\u00e1ximo 40 caracteres."
    if not ALLOWED_EMAIL_PATTERN.fullmatch(form_data["email"] or ""):
        errors["email"]="Digite um e-mail v\u00e1lido do Gmail, Hotmail, Outlook ou Yahoo."
    if form_data["confirma_dados"]!="sim":
        errors["confirma_dados"]="Confirme os dados para finalizar a inscri\u00e7\u00e3o."
    return errors
def error_step(errors):
    if "confirma_dados" in errors: return "revisao"
    if "local_id" in errors or "curso_id" in errors or "opcao_id" in errors: return "escolher"
    return "dados"
def render_wizard(form_data=None, errors=None, current_step="index"):
    fd = form_data or get_default_form_data()
    selected_option = get_course_option(fd.get("opcao_id")) or COURSE_INFO
    return render_template_string(
        TEMPLATE_WIZARD,
        course_info=selected_option,
        local_options=LOCAL_OPTIONS,
        course_catalog=COURSE_CATALOG,
        course_options=COURSE_OPTIONS,
        current_step=current_step,
        errors=errors or {},
        form_data=fd,
        generos=["Feminino","Masculino","Outro","Prefiro n\u00e3o dizer"],
    )
@app.route("/",methods=["GET"])
def home(): return render_wizard()
@app.route("/inscricao",methods=["GET","POST"])
def inscricao_unica():
    if request.method=="GET": return redirect(url_for("home"))
    form_data = get_default_form_data(request.form)
    errors    = validate_form_data(form_data)
    if errors: return render_wizard(form_data=form_data,errors=errors,current_step=error_step(errors))
    protocolo = str(uuid.uuid4())[:8].upper()
    session["protocolo"] = protocolo
    dados = [
        protocolo, form_data["nome"], form_data["genero"], form_data["cpf"],
        form_data["nascimento"], form_data["whatsapp"], form_data["email"],
        form_data["cep"], form_data["bairro"], form_data["local"],
        form_data["curso"], form_data["turma"], form_data["dias_aula"],
        form_data["horario"], form_data["data_inicio"], form_data["encerramento"],
        form_data["endereco_curso"], form_data["como_conheceu"],
    ]
    try: append_to_sheet(dados)
    except Exception as exc: print("Erro ao salvar na planilha:",exc); traceback.print_exc()
    try:
        response = send_registration_to_supabase(form_data)
        print("Envio para Supabase concluido:",response.status_code)
    except Exception as exc: print("Erro ao enviar para Supabase:",exc)
    return redirect(url_for("confirmacao"))
@app.route("/curso",methods=["GET","POST"])
@app.route("/revisao",methods=["GET","POST"])
@app.route("/wizard",methods=["GET"])
def legacy_routes(): return redirect(url_for("home"))
@app.route("/confirmacao",methods=["GET"])
def confirmacao():
    protocolo = session.get("protocolo")
    if not protocolo: return redirect(url_for("home"))
    home_url = "https://movimenta-rio-guadalupe.onrender.com"
    return render_template_string(
        TEMPLATE_CONFIRMACAO,
        protocolo=protocolo,
        whatsapp_share_url=build_whatsapp_share_url(home_url),
    )
# ── SUPABASE ──────────────────────────────────────────────────────────────────
import requests as _requests
SUPABASE_FUNCTION_URL = os.environ.get("SUPABASE_FUNCTION_URL","https://egpyhfzatabyftwajoad.supabase.co/functions/v1/fgm-register")
SUPABASE_API_KEY = os.environ.get("SUPABASE_API_KEY","jyUskwXkc54ZcMPyADLFN6LvZO0I60e3")
def normalize_phone_number(phone):
    digits = re.sub(r"[^\d]","",phone or "")
    return f"55{digits}" if len(digits)==11 else digits
def send_registration_to_supabase(form_data):
    phone = normalize_phone_number(form_data.get("whatsapp",""))
    payload = {
        "name":form_data.get("nome",""),"phone":phone,
        "curso":form_data.get("curso",""),"local":form_data.get("local",""),
        "dia_semana":form_data.get("dias_aula",""),"dias_semana":form_data.get("dias_aula",""),
        "data_inicio":form_data.get("data_inicio",""),"data_inscricao":datetime.utcnow().isoformat()+"Z",
        "horario":form_data.get("horario",""),
    }
    headers = {"Content-Type":"application/json","Accept":"application/json","x-api-key":SUPABASE_API_KEY,"Authorization":f"Bearer {SUPABASE_API_KEY}"}
    response = _requests.post(SUPABASE_FUNCTION_URL,headers=headers,json=payload,timeout=10)
    if not response.ok: raise RuntimeError(f"Supabase retornou {response.status_code}: {response.text[:500]}")
    return response
if __name__=="__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)
