"""CONVERSA LIVRE: roteador de pergunta -> folha de fatos [F#] de TODAS as fontes do Sulco, sem LLM.

O agricultor pode perguntar de qualquer assunto que o Sulco tenha dado, a qualquer momento ("quando começa a chover aqui", "o milho aguenta seca",
"quantos dias o feijão demora", "posso plantar milho com feijão junto", "por que o sorgo não aparece", "quanto custa a semente"). Este módulo:
  1. acha o(s) TEMA(s) da pergunta por regras e palavras (com tolerância a erro de grafia; nada de LLM);
  2. acha a(s) cultura(s) (a extração de `intencao`, com grafia aproximada) e o local;
  3. monta SÓ os fatos relevantes, cada um com texto, texto_simples, origem e marca de lacuna;
  4. quando o assunto é algo que NÃO temos (preço, custo, semente, venda, lucro, produtividade...), devolve a lacuna dita com franqueza e o que existe.
Nenhum número é escrito aqui: todo número vem de código/arquivo já lido pelas fontes (cada fato traz a origem). O LLM, quando ligado, só REESCREVE
estes fatos (`conversa._responder_com_fatos`); sem LLM, `texto_padrao_livre` já responde em frases simples.
"""
from __future__ import annotations

import difflib
import re
from functools import lru_cache

from . import fatos as FT
from . import intencao as IT
from . import sobre_sulco as _sulco
from .verificador import contar_palavras, limpar_citacoes, sem_acento

MAX_FATOS = 14                    # medição de 2026-11-15: a IA recebia 1 a 4 fatos e não tinha com o que analisar
TETO_TOKENS_LIVRE = 1100               # fatos da pergunta; o prompt todo (sistema + pergunta + fatos) fica abaixo de ~2.800 tokens
MAX_PALAVRAS_PADRAO = 56          # resposta falada: ~60 palavras
# PERGUNTA GRANDE (12+ palavras, 2+ temas ou pedido de explicação): o limite é dinâmico. Resposta ~110 palavras, até 8 fatos, frases curtas.
LIMITE_PALAVRAS_CURTA = 90        # o que o prompt pede para pergunta curta
LIMITE_PALAVRAS_GRANDE = 130      # o que o prompt pede para pergunta grande
MAX_PALAVRAS_PADRAO_GRANDE = 106  # texto padrão (sem IA) da pergunta grande
MAX_FATOS_GRANDE = 18
TETO_TOKENS_GRANDE = 1400          # fatos da pergunta grande; o prompt todo continua abaixo de 2.800 tokens (testado)
_PEDE_EXPLICACAO = re.compile(r"\b(explica\w*|explique\w*|por ?que|porque|como funciona|me conta|conta pra mim|conta para mim|me diga|detalha\w*)\b")
FECHO = "Converse com o técnico."
SEM_RESPOSTA = "Isso eu não achei nos dados do Sulco nem no material que tenho, e não quero chutar. Vale perguntar ao técnico."

# ------------------------------------------------------------------------------------------------ normalização e grafia
_LEXICO = ("chuva chover chove chovendo veranico seca solo terra fraco fraca plantar plantio plantei colheita colher semente sementes preco custo custa lucro "
           "dinheiro vender venda consorcio junto juntos rotacao erosao enxurrada satelite aguenta aguentar demora demorar ciclo calor quente temperatura "
           "adubo adubar adubacao praga pragas doenca irrigacao irrigar municipio planta produz produzir epoca quando comeca zoneamento argila areia evaporacao "
           "verde melhorar previsao financiamento credito mercado produtividade quantos quanto quantas cultura culturas inverno estiagem "
           "nitrogenio palhada palha forragem gado animais ensolarado sombra espacamento profundidade variedade cultivar vender compensa renda rendimento "
           "glossario significa explica funciona confiavel confia acerta modelo limite limites dados fonte fontes lacuna caminho caminhos sugestao "
           "sugeriu aparece aparecer depois antes repetir seguidas quantidade sacas saca toneladas quilos hectare hectares dias semanas meses mes").split()
_LEXICO_SET = set(_LEXICO)
_NAO_CORRIGIR = {"franca", "capital", "comprar", "carro", "novo", "nova", "jogo", "piada", "futebol"}      # palavras de fora do assunto que parecem do vocabulário


def _norm(msg: str) -> str:
    t = sem_acento(str(msg).lower())
    t = re.sub(r"[^a-z0-9%/ ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def corrigir_grafia(n: str) -> str:
    """Troca palavras parecidas com o vocabulário do Sulco ('prazo'... não): 'quano choverr' -> 'quando chover'. Só palavras de 5+ letras, mesma letra
    inicial e semelhança >= 0,84; palavra que já é do vocabulário (ou prefixo dele) fica como está."""
    out = []
    for w in n.split():
        if len(w) >= 5 and w not in _NAO_CORRIGIR and w not in _LEXICO_SET and not any(v.startswith(w) for v in _LEXICO_SET) and not w.isdigit():
            cands = [v for v in _LEXICO if v[0] == w[0] and abs(len(v) - len(w)) <= 2]
            par = difflib.get_close_matches(w, cands, n=1, cutoff=0.84)
            if par:
                w = par[0]
        out.append(w)
    return " ".join(out)


# ------------------------------------------------------------------------------------------------ temas
# (tema, regex sobre o texto normalizado e corrigido). A ORDEM é a prioridade quando a pergunta casa vários.
_T = [
    # --- o que NÃO temos (lacunas honestas)
    ("preco", r"\bprec[oa]s?\b|cotacao|quanto (custa|custam|vale|valem|pagam|paga|vendem|vende|se paga)|valor (da|do|de|das|dos) (saca|venda|semente|sementes|producao)|\bpagam\b"),
    ("custo", r"\bcusto|\bcustar|quanto (gasto|gasta|se gasta|preciso gastar|investir)|investimento|financiament|credito|emprestimo|\bseguro\b|proagro|pronaf|subsidio|\bbanco\b|\bgastar? (com|de) |gast(ar|o|a) (pra|para|com|de|no|na)|quanto (vou|vai|tenho|preciso).{0,12}gast"),
    ("semente", r"semente|\bmudas?\b|variedade|cultivar|\bmaniva\b|onde (compro|comprar|acho|consigo|encontro)|sementes? crioula"),
    ("venda", r"\bvend(er|o|a|em|ido)\b|comprador|\bmercado\b|atravessador|\bfeira\b|cooperativ|comercializ|escoar|entregar a producao|compensa vender"),
    ("lucro", r"lucr|\bdinheiro\b|ganhar|\bganhos?\b|rentab|compensa|vale a pena|faturar|\bpaga bem|sair no lucro|\brico\b|vou ficar bem"),
    ("produtividade", r"produtividade|quantas? sacas?|quantos? (quilos|kg|toneladas|kilos)|quanto (vou |vai |posso |iria |ira )(colher|produzir|tirar|render|apurar)|quanto (da|produz|rende|colhe|colhem)|safra (boa|ruim|vai|sera)|colheita (boa|ruim|vai|sera)|\brendimento\b|\brende quanto"),
    ("pragas", r"\bpragas?\b|doenca|lagarta|pulgao|fungo|ferrugem|mosca|inseto|veneno|defensivo|agrotoxic|cigarrinha|nematoide|mancha"),
    ("adubo", r"\badubo|adubar|adubacao|fertiliz|calcario|esterco|\bnpk\b|ureia|\bcalagem|quimic"),
    ("irrigacao", r"irrig|\bpoco\b|\bacude\b|gotejo|gotejament|aspersao|\bpivo\b|regar|\brega\b|agua do rio|carro pipa"),
    ("manejo", r"espacamento|densidade|profundidade (da|do|de) (plantio|semeadura)|como (se )?planta|como plantar|modo de plantar|capina|\btratos? cultura|poda|desbaste|\bcova\b|armazen|secagem|beneficiamento|\bdose\b|quantidade de semente"),
    ("clima_futuro", r"vai (chover|ter chuva|ter seca|ter veranico|haver chuva|dar chuva|dar seca|ser (um )?(bom |mau |ruim )?(inverno|ano))|chovera|previs\w+ d[aeo]s? (chuva|clima|tempo|inverno)|prev(er|e) (a )?(chuva|clima|tempo)|inverno (vai ser|sera)|(esse|este|proximo) (ano|inverno).{0,25}(chuv|seca)|quando (vai|vem|volta) (a )?chuva|vai faltar chuva"),
    ("chuva_atual", r"(costuma|chove|chover|chuva|chovendo|choveu|chovem).{0,25}(nessa|essa|nesta|esta|neste|nesse|dessa|desta) (epoca|mes|periodo|tempo)|(nessa|essa|nesta|esta) epoca do ano.{0,25}(chov|chuv)|choveu (muito|pouco|bem|bastante|mais|menos|o suficiente)|(esse|este) ano.{0,20}(choveu|chuva)|(choveu|chuva).{0,20}(esse|este) ano|chove (muito |pouco |mais )?em (janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)|(chuva|chove|chover).{0,12}(agora|hoje|esse mes|neste mes)"),
    ("plantar_agora", r"(o que|que (planta|cultura|plantas|culturas)).{0,25}(plantar|planto|da pra plantar|da para plantar|posso plantar|se planta).{0,25}(nessa|essa|nesta|esta|neste|nesse|agora|hoje) ?(epoca|mes|periodo|tempo)?|(nessa|essa|nesta|esta) epoca.{0,25}(plantar|planto|plantio)|(plantar|planto) (nessa|nesta|esta|essa) epoca|o que (da|posso|devo) (plantar )?agora"),
    # --- clima do local
    ("veranico", r"veranico|dias? (seguidos? )?sem chuva|dias? .{0,15}sem (chuva|chover)|chuva falha|falhou a chuva|para de chover|estiagem (no meio|dentro)|chuva (ficou|fica) (parada|falhando)"),
    ("chuva_epoca", r"(quando|que (mes|meses|epoca)|em que (mes|epoca)|comeca|comecam|inicio|vem|chega|volta).{0,28}(chov|chuv|inverno|aguas|quadra)|epoca d[aeo]s? (chuva|aguas|inverno)|estacao chuvosa|\bquadra\b|chove (mais|pouco|muito|bem)|quanto (chove|de chuva)|chuva (media|por ano|normal|do ano)|pluviosidade|meses? (de|da) chuva|tempo d[aeo]s? (chuva|aguas)|\binverno\b|aguas (do|de) (inverno|ano)|chuvas? (aqui|na regiao|no municipio)"),
    ("solo_nu", r"(solo|terra|chao) (\w+ )?(fica|esta|costuma ficar|fica de|vira) (nu|nua|descoberto|descoberta|pelad\w+|exposto|exposta)|solo nu|terra nua|terra descoberta|solo descoberto|chao nu|sem verde|terra pelada|terra (fica|costuma ficar) (nua|descoberta|exposta)|fica descoberta|cobertura do solo"),
    ("estresse", r"estress|\bsofr\w+|epoca ruim|planta(s)? (fica|ficam) (fraca|fracas)|pior epoca|epoca mais dificil"),
    ("extremos", r"dias? (muito )?quentes?|calor (forte|demais|extremo|exagerado)|onda de calor|temporal|chuva (muito )?forte|chuva extrema|tempestade|rajada|maior chuva"),
    ("agua_balanco", r"da conta d[ae]|calor tira|a agua que (o calor|a planta|evapora)|evapora|evapotransp|\beto\b|falta (de )?agua|balanco hidrico|\bsaldo\b|agua (no|do|da) (solo|terra)|umidade|seca (demais|de mais|todo|o ano)|\bseco\b (o|todo)"),
    ("erosao", r"erosao|enxurrada|(levar|leva|lavar|lava|carregar|carrega|arrastar|arrasta) a terra|escoamento|ravina|declive|terreno inclinado|ladeira|barranco|perda de solo"),
    # --- previsão, modelo, limites, sobre o Sulco
    ("previsao", r"previs|prever|\bo verde\b|verdor|vegetacao|vai (melhorar|piorar|ficar|estar)|proxim\w+ (semana|dia|quinzena|mes)|nas proximas|\bndvi\b|satelite (mostra|ve|diz)|amanha|mes que vem"),
    ("modelo", r"\bmodelo\b|acerta|confiavel|confio|confiar|\bskill\b|metrica|precisao|incerteza|margem de erro"),
    ("limites", r"satelite.{0,20}de onde|de onde.{0,20}satelite|\blimites?\b|de onde (vem|vêm|veem) (os )?dados|fonte dos dados|\bfontes?\b|enxerga|resolucao|nao sabe|nao consegue|\bconfiavel\b.*dados|dados (sao|vem|vêm) (de|do|da)|de que ano|qual (a )?data|dados .{0,10}(atuais|recentes|antigos)|ate (que )?quando"),
    ("sobre_sulco", r"quais (dados|informacoes|coisas) (voces|vc|o sulco)|o que (voces|vc) tem|o que o sulco (tem|sabe)|o que (e|faz|eh) (o )?sulco|como o sulco (funciona|decide|calcula|escolhe|sugere|faz|sabe)|como (funciona|voce funciona|o sulco funciona|isso funciona|e feito|calcula|decide)|para que serve|pra que serve|quem fez|o que (voce|vc) (faz|sabe|consegue|tem)|o que posso perguntar|em que (voce|vc) (ajuda|pode ajudar)"),
    ("glossario", r"o que (e|eh|sao|significa|quer dizer)\b|\bsignifica|quer dizer|me explica|explica (o|a|isso)|o que (e|eh) isso"),
    # --- culturas, solo, época
    ("consorcio", r"\bjunt[oa]s?\b|consorci|misturad|misturar|ao mesmo tempo|intercal|na mesma (area|terra|roca|cova|linha)|\bler\b|plantar (com|e) \w+ (e|com)|\bcom o\b.{0,12}\bjunto"),
    ("rotacao_par", r"\b(depois|apos|antes) d[eoa]s?\b|vem depois|plantar depois|em seguida|na sequencia|repetir|mesmo lugar|(dois|tres|varios) anos seguidos|seguidas?\b|sucessao|revezar|proxima (safra|cultura)"),
    ("rotacao_conceito", r"rotacao|rotacionar|alternar|revezamento|girar (as )?cultura|trocar (de )?cultura|mudar (de )?cultura"),
    ("por_que_nao", r"(nao|nunca) (aparece|aparecem|apareceu|sugeriu|sugere|indicou|indica|entrou|entra|foi sugerid|esta na lista|ta na lista)|(sumiu|sumiram|ficou de fora|fora da lista|nao (da|dao) certo)|por que (nao|so)|porque (nao|so)|por que .{0,25}(nao|so) (aparece|da|serve|entra)"),
    ("zarc_plantio", r"quando (posso |devo |da pra |da para |e bom |se pode |eu posso )?plantar|epoca (certa|boa|ideal|indicada|de plantio|do plantio|para plantar|pra plantar)|que (mes|epoca) (se )?(plantar|planta|planto|e bom|posso plantar|devo plantar)|\bzarc\b|zoneamento|\bjanela\b|plantar (agora|hoje|cedo|tarde)|melhor (mes|epoca|data)|mes (certo|ideal|bom) |cedo demais|tarde demais|data de plantio|posso plantar (em|no|agora)|ja (da|posso) plantar|comecar a plantar"),
    ("ciclo", r"quantos dias|dias (demora|leva|dura|para colher|pra colher|de ciclo)|demora(r)? (para|pra|a)? ?(colher|crescer|dar|nascer|florescer)|(?<!um )(?<!meu )(?<!esse )(?<!este )\bciclo (do|da|de|dos|das|dele|dela|leva|dura|demora)\b|\b(qual|quanto|quantos|como e) (e )?(o )?ciclo\b|quando (se )?(colhe|colho|colher|vai colher|da a colheita)|tempo (de|para|pra) (colher|colheita|crescer)|fases?\b|quanto tempo|meses? (para|pra) colher|duracao|colhe em quantos|\bdemora\b|\bleva quanto"),
    ("cultura_clima", r"aguent(a|am|ar)|resist(e|em|ente|encia)|tolera|\bsuporta|precisa(m)? de (muita |pouca )?(agua|chuva|sol|calor)|quanta (agua|chuva)|chuva (minima|maxima|que (precisa|gosta))|temperatura (ideal|boa|da|maxima|minima|que)|faixa de (chuva|temperatura|calor)|\bfrio\b|geada|da bem|se da bem|calor demais|(muito|pouco) (calor|sol|chuva)|\bsol forte|passa fome de agua|passa sede|morre (de sede|sem chuva)"),
    ("viabilidade", r"(da|dao|dara|darao) (certo|bem|pra|para)|\bserve\b|serve(m)? (aqui|pra mim|para mim)|consigo plantar|posso plantar|da pra plantar|da para plantar|vai bem aqui|vale plantar|aqui da|pode plantar|\bviavel\b|\bviabilidade"),
    ("solo", r"acidez|acidific|\bchao\b|\bsolo\b|\bterra (e |esta |ta |eh )?(fraca|cansada|ruim|fraco|pobre|seca|arenosa|dura|salgada|acida|boa)|argila|areia|arenos|\bbarro|textura|fertil|\bph\b|acido|acida|materia organica|\bfraca\b|\bfraco\b|salin|soilgrids|tipo de (solo|terra)|qualidade da terra|\bterra\b"),
    ("adubacao_verde", r"adubacao verde|adubo verde|leguminosa|fixa(r|m)? nitrogenio|nitrogenio|\bn\b (no|do|da) solo|planta(s)? que (adubam|enriquecem|melhoram|recuperam)|recuperar (a )?terra|melhorar (o )?solo"),
    ("palhada", r"palhada|\bpalha\b|cobertura morta|plantio direto|deixar (a )?palha|restos de cultura|resto da cultura|cobrir o solo"),
    ("forragem", r"forrageira|forragem|\bgado\b|\bbode\b|\bcabra\b|ovelha|animais|\bracao\b|silagem|\bpasto\b|alimento (para|pro|dos) animais|comida (para|pro|dos) (gado|animais)"),
    ("pam", r"o que (o |a |os |as )?(municipio|cidade|regiao|gente|povo|pessoal|vizinho|agricultores?|produtores?|aqui|por aqui).{0,25}(planta|produz|colhe|cultiva|mais)|mais (plantad|produzid|cultivad|colhid)|principais? (cultura|lavoura|planta|producao)|o que (se )?planta (aqui|por aqui|na regiao|no municipio)|que (cultura|lavoura|planta)s? .{0,12}(aqui|municipio|regiao)|\bpam\b|\bibge\b|area plantada|area colhida|quanto se planta|quem planta"),
]
TEMAS = [(t, re.compile(r)) for t, r in _T]
ORDEM_TEMA = {t: i for i, (t, _) in enumerate(_T)}
TEMAS_LACUNA = {"clima_futuro", "preco", "custo", "semente", "venda", "lucro", "produtividade", "pragas", "adubo", "irrigacao", "manejo"}
TEMAS_RAG = {"pragas", "adubo", "manejo", "irrigacao", "rotacao_conceito", "forragem", "palhada", "adubacao_verde", "semente"}
TEMAS_LOCAL = {"chuva_atual", "plantar_agora", "chuva_epoca", "veranico", "solo_nu", "estresse", "extremos", "agua_balanco", "erosao", "previsao", "modelo", "solo", "pam", "zarc_plantio",
               "viabilidade", "por_que_nao", "cultura_clima"}
# palavras que o agricultor usa para chamar os temas ao falar de uma cultura sem dizer o nome dela (usa a cultura da conversa)
_USA_CULTURA = {"ciclo", "cultura_clima", "viabilidade", "zarc_plantio", "por_que_nao", "consorcio", "rotacao_par", "solo", "produtividade", "venda", "preco",
                "semente", "pragas", "adubo", "lucro"}

_MESES_N = {"janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"}
_PERGUNTA = re.compile(r"^(quando|onde|quanto|quanta|quantos|quantas|qual|quais|como|por ?que|porque|o que|que |posso|pode|podem|podemos|da pra|da para|tem |tem$|existe|ha |vai |"
                       r"aguenta|serve|devo|vale|compensa|consigo|se eu|sera|eh |e (bom|ruim|verdade|possivel)|me (diz|diga|fala|fale|explica|explique|conta|conte|mostra|mostre)|"
                       r"queria saber|quero saber|gostaria de saber|tenho uma duvida|minha duvida|duvida|preciso saber|ja (da|posso)|dar(ia)? pra|e (se|que)|sera que|ainda|meu|minha|nosso|"
                       r"aqui|nessa|nesse|essa|esse|isso|a (chuva|terra|planta|cultura)|o (milho|feijao|solo|verde|sorgo)|ele |ela |e o |e a |e se)")
_SO_QUESTAO = re.compile(r"\?|\be agora\b|\bqual a|\bme (diz|diga|fala|fale|explica)|\bpor que\b|\bporque\b|\bsera que\b|\bnao sei\b|\bqueria saber\b|\bduvida\b")


def parece_pergunta(msg: str) -> bool:
    """A mensagem tem cara de pergunta (e não de resposta curta a uma pergunta do sistema)?"""
    n = _norm(msg)
    return bool("?" in str(msg) or _PERGUNTA.search(n) or _SO_QUESTAO.search(n))


def pergunta_grande(pergunta) -> bool:
    """Pergunta que pede resposta mais longa: 12+ palavras, junta 2+ temas ou pede explicação ('explica', 'por que', 'como funciona', 'me conta')."""
    n = _norm(pergunta)
    if len(n.split()) >= 12 or _PEDE_EXPLICACAO.search(n):
        return True
    try:
        return len(detectar_temas(pergunta)) >= 2
    except Exception:  # noqa: BLE001
        return False


def detectar_temas(pergunta: str) -> list[str]:
    """Temas da pergunta na ordem de prioridade do roteador (sem LLM). Tolera erro de grafia (corrige palavras parecidas com o vocabulário)."""
    n = _norm(pergunta)
    nc = corrigir_grafia(n)
    ach = [t for t, r in TEMAS if r.search(n) or (nc != n and r.search(nc))]
    # "vale a pena plantar X aqui?" / "compensa plantar X?": a pessoa quer saber se a cultura COMBINA com o lugar. Não é pedido de lucro:
    # responde com o clima, o zoneamento e a época, e diz numa frase que preço e custo o Sulco não tem (medição de 2026-11-15).
    if "lucro" in ach and re.search(r"vale a pena|compensa|\bserve\b|da certo", nc) and not re.search(r"lucr|dinheiro|ganh|fatur|\brico\b|financeir|rentab|paga", nc):
        ach = [t for t in ach if t != "lucro"]
        for t in ("cultura_clima", "zarc_plantio", "preco"):
            if t not in ach:
                ach.append(t)
    # 'terra' sozinho (tema solo) só vale sem tema de lacuna/clima mais específico
    if "solo" in ach and len(ach) > 1 and re.fullmatch(r".*", n) and not re.search(r"\bsolo\b|argila|areia|arenos|textura|fertil|\bph\b|acid|fraca|fraco|cansada|pobre|ruim", nc):
        ach.remove("solo")
    if "glossario" in ach and len(ach) > 1:        # 'o que é veranico' é sobre o veranico; o glossário só entra sozinho
        ach.remove("glossario")
    if "rotacao_conceito" in ach and "rotacao_par" in ach:
        ach.remove("rotacao_conceito")
    if "viabilidade" in ach and ("cultura_clima" in ach or "zarc_plantio" in ach or "consorcio" in ach):
        ach.remove("viabilidade")
    if "lucro" in ach and "produtividade" in ach:
        ach.remove("produtividade")
    if "preco" in ach and ("venda" in ach or "lucro" in ach or "semente" in ach):
        ach = [t for t in ach if t not in ("venda", "lucro")] if "semente" in ach else [t for t in ach if t != "venda"]
    if "adubacao_verde" in ach:
        ach = [t for t in ach if t not in ("adubo", "previsao", "glossario", "solo")]
    if "forragem" in ach:
        ach = [t for t in ach if t not in ("viabilidade", "solo")]
    if "rotacao_par" in ach:
        ach = [t for t in ach if t not in ("viabilidade", "zarc_plantio")]
    if "solo" in ach and "viabilidade" in ach and re.search(r"\bph\b|\bsolo\b|textura|argila|areia", nc):
        ach.remove("viabilidade")
    if "chuva_atual" in ach and "clima_futuro" in ach:
        ach.remove("chuva_atual")
    if "chuva_atual" in ach:
        ach = [t for t in ach if t not in ("chuva_epoca", "ciclo", "clima_futuro", "solo_nu", "estresse")]
    if "plantar_agora" in ach:
        ach = [t for t in ach if t not in ("chuva_epoca", "zarc_plantio", "viabilidade", "solo_nu", "chuva_atual", "sobre_sulco")]
    if "veranico" in ach:
        ach = [t for t in ach if t not in ("chuva_epoca", "ciclo")]
    if "modelo" in ach and "previsao" in ach:
        ach.remove("previsao")
    if "estresse" in ach and "previsao" in ach and not re.search(r"previs|prever|proxim|vai (melhorar|piorar|ficar|estar)|amanha|mes que vem", nc):
        ach.remove("previsao")      # "quando a vegetação costuma sofrer" pergunta do passado: não mistura a previsão
    if "zarc_plantio" in ach and "chuva_epoca" in ach and not re.search(r"plant", nc):
        ach.remove("zarc_plantio")
    if "limites" in ach and "sobre_sulco" in ach:
        ach.remove("sobre_sulco")
    return ach


# ------------------------------------------------------------------------------------------------ montagem de fatos
def _f(tema: str, rotulo: str, simples: str, origem: str, *, lacuna: bool = False, prio: int = 2, texto: str | None = None, qual: str | None = None) -> dict:
    """`qual` = a MESMA frase sem número (versão qualitativa, usada quando o usuário não pediu número). Sem `qual` e com dígito, `qualificar` tenta; se não der, o fato sai."""
    s = " ".join(str(simples).split())
    return {"qual": qual, **{"tema": tema, "rotulo": rotulo, "texto": " ".join((texto or s).split()), "texto_simples": s, "origem": origem, "lacuna": lacuna, "prio": prio,
            "papel": "livre"}}


# ---------- números só se o usuário pedir
_PEDE_NUMERO = re.compile(r"\d|\b(um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|vinte|trinta|quarenta|cinquenta|cem|cento|mil)\b.{0,12}\b(dias?|meses|mes|anos?|mm|graus|hectares?|quilos?|kg|sacas?|reais|por cento)\b|"
                         r"\b(mm|milimetros?|graus|%|por ?cento|percentual|porcentagem|hectares?|kg|quilos?|toneladas?|reais|numero|numeros|quanto|quantos|quantas|quanta)\b|"
                         r"qual a (temperatura|media|quantidade|area)|em media quant|me d[aá] o numero|que numero|tem quantos|quantidade")


def numeros_permitidos(msg: str, estado: dict | None = None) -> bool:
    """O usuário trouxe ou pediu número NESTE turno (dígito, numeral por extenso com unidade, unidade, 'quanto/quantos...')? Vale só para este turno."""
    n = _norm(msg)
    return bool(_PEDE_NUMERO.search(n))


_NUM_EXTENSO = re.compile(r"\b(dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|quinze|vinte|trinta|quarenta|cinquenta|sessenta|cem|cento|mil|milhao|milhoes|metade|dobro|triplo)\b")


def tem_numero(texto: str) -> bool:
    """Dígito ou numeral por extenso (um/uma ficam: são artigo) no texto já sem as marcas [F#]."""
    t = limpar_citacoes(texto)
    return bool(re.search(r"\d", t) or _NUM_EXTENSO.search(sem_acento(t.lower())))


def _bin_dias(n: int) -> str:
    return "poucos dias" if n <= 3 else "alguns dias" if n <= 15 else "muitos dias"


def qualificar(t: str) -> str | None:
    """Versão sem número de uma frase que tem dígito (regras fixas, só troca por palavras); None = não dá, o fato sai da resposta."""
    if not re.search(r"\d", t):
        return t
    t = re.sub(r"\s*\(\d{2}/\d{2}/\d{4}\)", "", t)
    t = re.sub(r"até \d{1,2}/(\d{1,2})/\d{4}", lambda m: "até " + _MESES[int(m.group(1)) - 1], t)
    t = re.sub(r"No ano de \d{4}", "No último ano", t)
    t = re.sub(r"[;,]? a maior chuva em um dia foi de [\d.,]+ mm", "", t)
    t = re.sub(r"de cerca de \d+ km", "de dezenas de quilômetros", t)
    t = re.sub(r"(?:uns|cerca de) (\d+) dias", lambda m: _bin_dias(int(m.group(1))), t)
    t = re.sub(r"\b(\d+) dias\b", lambda m: _bin_dias(int(m.group(1))), t)
    t = re.sub(r"em (\d+(?:,\d+)?)% dos \d+ anos( olhados)?", lambda m: _pct_qual(float(m.group(1).replace(",", ".")) / 100) + " dos anos olhados", t)
    return None if re.search(r"\d", t) else t


_TROCAS_EXTENSO = [(r"as próximas duas semanas", "as próximas semanas"), (r"duas semanas", "poucas semanas"), (r"três caminhos", "caminhos"), (r"duas alternativas", "alternativas"),
                   (r"\bdois ou mais\b", "vários"), (r"\bduas culturas\b", "culturas"), (r"\bdois anos\b", "alguns anos"), (r"\bdois lados\b", "lados")]


def _sem_extenso(t: str) -> str:
    for a, b in _TROCAS_EXTENSO:
        t = re.sub(a, b, t)
    return t


def sem_numeros(fatos: list[dict]) -> list[dict]:
    """Fatos na versão QUALITATIVA (texto_simples sem número). O original fica em 'texto'. Fato sem versão possível é descartado."""
    out = []
    for f in fatos:
        q = f.get("qual") or qualificar(f["texto_simples"])
        q = _sem_extenso(q) if q else q
        if q and not tem_numero(q):
            out.append({**f, "texto_simples": " ".join(q.split()), "numeros": False})
        elif not f.get("lacuna"):
            out.append({**f, "so_comparar": True})      # sem versão em palavras: vai com o número, e a IA é instruída a dizer só a comparação
    return out


@lru_cache(maxsize=1)
def _nomes() -> dict:
    from src.app import mvp as M
    return dict(M.culturas_disponiveis())


def _art(cid: str, tipo: str = "o") -> str:
    from . import dialogo as D
    return D.nome_com_artigo(cid, _nomes(), tipo)


def _nome(cid: str) -> str:
    return str(_nomes().get(cid, cid)).lower()


def _lista(ids: list[str]) -> str:
    from . import dialogo as D
    return D.lista_ptbr([_nome(c) for c in ids])


@lru_cache(maxsize=8)
def _folha_local(ponto_id: str) -> dict:
    return FT.montar_folha(ponto_id, None, "sem")


@lru_cache(maxsize=1)
def _tabela() -> dict:
    from src.culturas import tabela_culturas as TC
    return TC.carregar()


def _atr(cid: str, chave: str):
    a = ((_tabela().get(cid) or {}).get("atributos") or {}).get(chave)
    return a["valor"] if a else None


def _do_folha(ponto: str | None, pares: list[tuple[str, str]], tema_novo: str, prio_max: int = 3) -> list[dict]:
    """Fatos da folha do local (com texto_simples) por (tema, rotulo); rotulo '*' = todos do tema."""
    if not ponto:
        return []
    try:
        fol = _folha_local(ponto)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for tema, rot in pares:
        for f in fol["fatos"]:
            if f["tema"] == tema and (rot == "*" or f["rotulo"] == rot) and f.get("texto_simples") and f["prio"] <= prio_max:
                out.append({**f, "tema": tema_novo, "papel": "livre"})
    return out


def _sem_local(tema: str, o_que: str) -> dict:
    return _f(tema, "sem município", f"Para dizer {o_que} do seu local, eu preciso saber o município.", "conversa: município não informado", lacuna=True, prio=1)


# ---------- cultura
def _ibge(ponto: str | None):
    if not ponto:
        return None
    try:
        import pandas as pd
        from src.app import mvp as M
        v = M.carregar_pontos().set_index("ponto_id").loc[ponto].get("ibge")
        return None if pd.isna(v) else int(v)
    except Exception:  # noqa: BLE001
        return None


def _ciclo_qual(dias) -> str:
    return "curto, de poucos meses" if dias <= 100 else "médio, de alguns meses" if dias <= 150 else "longo, de muitos meses"


def _fatos_ciclo(cid: str) -> list[dict]:
    from src.culturas import ciclo_fao as CF
    fao = CF.ciclos_fao().get(cid)
    out = []
    if fao:
        o = "data/culturas/fao_staging.csv via src.culturas.ciclo_fao (FAO Irrigation and Drainage Paper 56)"
        e = fao.get("estagios") or []
        out.append(_f("ciclo", f"ciclo de {cid}", f"Pela referência da FAO (de outras regiões), {_art(cid)} leva uns {fao['dias']} dias do plantio até a colheita. "
                      "A sua semente pode ser diferente.", o, prio=1,
                      qual=f"Pela referência da FAO (de outras regiões), {_art(cid)} tem ciclo {_ciclo_qual(fao['dias'])} do plantio até a colheita. A sua semente pode ser diferente."))
        if len(e) == 4:
            out.append(_f("ciclo", f"fases de {cid}", f"Nessa referência, são {e[0]} dias de começo, {e[1]} de crescimento, {e[2]} no meio do ciclo e {e[3]} até o fim.", o, prio=2))
        if fao.get("dias_min") and fao.get("dias_max") and fao["dias_min"] != fao["dias_max"]:
            out.append(_f("ciclo", f"variação do ciclo de {cid}", f"Conforme o lugar e a época de plantio, a FAO traz de {fao['dias_min']} a {fao['dias_max']} dias para {_art(cid)}.", o, prio=3))
    else:
        lo, hi = _atr(cid, "ciclo_min_dias"), _atr(cid, "ciclo_max_dias")
        if lo and hi:
            out.append(_f("ciclo", f"ciclo de {cid}", f"Para {_art(cid)} não temos o ciclo da FAO. A referência geral (EcoCrop) diz que vai de {FT.br(lo, 0)} a {FT.br(hi, 0)} dias, "
                          "conforme a semente e o lugar; é uma faixa larga.", "data/culturas/tabela_culturas.csv (FAO EcoCrop)", prio=1,
                          qual=f"Para {_art(cid)} não temos o ciclo da FAO. A referência geral (EcoCrop) dá uma faixa larga de dias, conforme a semente e o lugar."))
        else:
            out.append(_f("ciclo", f"ciclo de {cid}", f"Ainda não temos o ciclo em dias {_art(cid, 'do')}.", "data/culturas/tabela_culturas.csv", lacuna=True, prio=1))
    return out


def _fatos_faixas(cid: str) -> list[dict]:
    o = "data/culturas/tabela_culturas.csv (FAO EcoCrop, faixa geral da espécie)"
    out = []
    cm, co1, co2, cx = (_atr(cid, k) for k in ("chuva_min_abs_mm", "chuva_otima_min_mm", "chuva_otima_max_mm", "chuva_max_abs_mm"))
    if co1 and co2 and cm:
        out.append(_f("cultura_clima", f"chuva de {cid}", f"Para {_art(cid)}, a faixa boa de chuva ao longo do ano vai de {FT.milhar(co1)} a {FT.milhar(co2)} mm; "
                      f"abaixo de {FT.milhar(cm)} mm ela costuma passar falta de água. É uma faixa geral da planta, não da sua semente.", o, prio=1,
                      qual=f"Para {_art(cid)}, existe uma faixa boa de chuva ao longo do ano; com chuva abaixo dela, a planta costuma passar falta de água. É uma faixa geral da planta, não da sua semente."))
    to1, to2, tmn, tmx = (_atr(cid, k) for k in ("temp_otima_min_c", "temp_otima_max_c", "temp_min_abs_c", "temp_max_abs_c"))
    if to1 and to2:
        out.append(_f("cultura_clima", f"calor de {cid}", f"A temperatura boa para {_art(cid)} fica entre {FT.br(to1, 0)} e {FT.br(to2, 0)} graus"
                      + (f"; abaixo de {FT.br(tmn, 0)} ou acima de {FT.br(tmx, 0)} graus ela sofre." if tmn and tmx else "."), o, prio=2,
                      qual=f"{_art(cid).capitalize()} tem uma faixa de temperatura boa; com frio ou calor demais, ela sofre."))
    d = _atr(cid, "demanda_hidrica_mm_ciclo")
    if d:
        out.append(_f("cultura_clima", f"água do ciclo de {cid}", f"Pela FAO, {_art(cid)} pede pelo menos uns {FT.milhar(d)} mm de água durante o ciclo todo.", o, prio=3))
    if not out:
        out.append(_f("cultura_clima", f"faixas de {cid}", f"Ainda não temos as faixas de chuva e calor {_art(cid, 'do')}.", o, lacuna=True, prio=1))
    return out


def _pct_qual(p: float) -> str:
    return "na maioria" if p >= 0.75 else "em boa parte" if p >= 0.5 else "em poucos"


def _fatos_viabilidade(cid: str, ponto: str | None, tema: str = "viabilidade") -> list[dict]:
    if not ponto:
        return [_sem_local(tema, "se dá certo")]
    from src.culturas import avaliar_sequencia as AS
    o = "src.culturas.avaliar_sequencia.avaliacao_local (motor.avaliar_local: clima 2001-2023, faixas EcoCrop e zoneamento)"
    try:
        av = AS.avaliacao_local(ponto)
    except Exception:  # noqa: BLE001
        return [_f(tema, f"viabilidade de {cid}", "Não consegui olhar agora se dá certo no seu local.", o, lacuna=True, prio=1)]
    v = (av.get("culturas") or {}).get(cid)
    if not v:
        return [_f(tema, f"viabilidade de {cid}", f"Ainda não temos dados {_art(cid, 'do')} para o seu local.", o, lacuna=True, prio=1)]
    n_anos = av["anos"][2] if isinstance(av.get("anos"), (list, tuple)) and len(av["anos"]) == 3 else None
    r = v.get("res") or {}
    if v["estado"] == "viavel":
        p = r.get("p_ano_viavel")
        ini = r.get("inicio")
        txt = f"No seu local, {_art(cid)} fica dentro das faixas de chuva e calor"
        if p is not None and n_anos:
            txt += f" em {FT.br(p * 100, 0)}% dos {n_anos} anos olhados"
        txt += (f", começando perto de {ini[:2]}/{ini[3:5]}" if ini and len(ini) == 5 else "") + ". É o que os dados mostram, não promessa de colheita."
        mes_ini = _MESES[int(ini[3:5]) - 1] if ini and len(ini) == 5 and ini[3:5].isdigit() else None
        qual = (f"No seu local, {_art(cid)} fica dentro das faixas de chuva e calor {_pct_qual(p)} dos anos olhados" if p is not None else f"No seu local, {_art(cid)} fica dentro das faixas de chuva e calor")
        qual += (f", começando perto de {mes_ini}" if mes_ini else "") + ". É o que os dados mostram, não promessa de colheita."
        return [_f(tema, f"viabilidade de {cid}", txt, o, prio=1, qual=qual)]
    if v["estado"] == "inviavel":                 # dados em conflito (EcoCrop x ZARC/PAM): não afirma que 'não dá'; diz que os dados não fecham
        cf = FT.fato_conflito(cid, ponto, _nomes())
        if cf:
            return [_f(tema, f"dados em conflito: {cid}", cf["texto_simples"], cf["origem"], lacuna=True, prio=1)]
    m = re.search(r"(\d+)% dos (\d+) anos.*melhor in[ií]cio: (\d+)%", " ".join(v.get("motivos") or []))
    qual_inv = None
    if m:
        txt = (f"No seu local, {_art(cid)} não ficou dentro das faixas de chuva e calor em pelo menos {m.group(1)}% dos {m.group(2)} anos em nenhuma época de plantio; "
               f"na melhor época foram só {m.group(3)}% dos anos. Por isso o Sulco não coloca {_art(cid)} entre as opções.")
        qual_inv = (f"No seu local, {_art(cid)} não ficou dentro das faixas de chuva e calor na maior parte dos anos em nenhuma época de plantio. Por isso o Sulco não coloca {_art(cid)} entre as opções.")
    elif v["estado"] == "inviavel":
        txt = f"Pelos dados do clima, {_art(cid)} não ficou dentro das faixas de chuva e calor com frequência suficiente no seu local."
    else:
        txt = f"Ainda não deu para avaliar {_art(cid)} no seu local: {'; '.join(v.get('lacunas') or ['falta dado'])[:120]}."
    return [_f(tema, f"viabilidade de {cid}", txt, o, lacuna=v["estado"] not in ("viavel", "inviavel"), prio=1, qual=qual_inv if m else None)]


def _fatos_zarc(cid: str, ponto: str | None) -> list[dict]:
    if not ponto:
        return [_sem_local("zarc_plantio", "a época de plantio")]
    c = FT._Coletor()
    try:
        FT._zarc(c, ponto, [cid])
    except Exception:  # noqa: BLE001
        return []
    out = []
    for f in c.fatos:
        if f.get("texto_simples"):
            out.append({**f, "tema": "zarc_plantio", "papel": "livre", "prio": 1})
    return out


def _fatos_janela(cid: str, ponto: str | None) -> list[dict]:
    """Melhor época pelos dados do clima (motor) e épocas de plantio mais usadas na região, sem prometer."""
    if not ponto:
        return []
    from src.culturas import avaliar_sequencia as AS
    try:
        v = (AS.avaliacao_local(ponto).get("culturas") or {}).get(cid) or {}
    except Exception:  # noqa: BLE001
        return []
    ini = (v.get("res") or {}).get("inicio")
    if v.get("estado") == "viavel" and ini and len(ini) == 5:
        return [_f("zarc_plantio", f"melhor começo de {cid}", f"Pelo clima dos últimos anos, o começo de plantio que mais deu certo para {_art(cid)} fica perto de {ini[:2]}/{ini[3:5]}. "
                   "Isso olha só chuva e calor.", "src.culturas.avaliar_sequencia.avaliacao_local (res.inicio)", prio=2,
                   qual=f"Pelo clima dos últimos anos, o começo de plantio que mais deu certo para {_art(cid)} fica perto de {_MESES[int(ini[3:5]) - 1]}. Isso olha só chuva e calor.")]
    return []


def _fatos_solo_cultura(cid: str, ponto: str | None) -> list[dict]:
    if not ponto:
        return []
    from src.culturas import solo_ecocrop as SE
    try:
        solo = SE.solo_do_ponto(ponto)
        nota = SE.nota_solo(cid, solo)
    except Exception:  # noqa: BLE001
        return []
    ph = (nota or {}).get("ph")
    if ph and solo and ph.get("faixa"):
        mn, omn, omx, mx = ph["faixa"]
        return [_f("solo", f"pH para {cid}", f"O pH estimado do solo da sua região é {FT.br(solo['ph_agua'], 1)}. Para {_art(cid)}, o pH bom vai de {FT.br(omn, 1)} a {FT.br(omx, 1)} "
                   f"(aceita de {FT.br(mn, 1)} a {FT.br(mx, 1)}). O pH vem de mapa global, não de análise do seu solo.", "src.culturas.solo_ecocrop (SoilGrids + EcoCrop)", prio=1,
                   qual=f"O pH estimado do solo da sua região está {'dentro da faixa boa' if omn <= solo['ph_agua'] <= omx else 'dentro do que ' + _art(cid) + ' aceita, mas fora da faixa boa' if mn <= solo['ph_agua'] <= mx else 'fora do que ' + _art(cid) + ' aceita'} "
                        f"para {_art(cid)}. O pH vem de mapa global, não de análise do seu solo.")]
    return []


@lru_cache(maxsize=64)
def _pam(ibge: int):
    import pandas as pd
    from src.culturas import renda as R
    d = pd.read_parquet(R.RAIZ / "data/processed/pam_ce.parquet")
    d = d[(d["ibge"] == ibge) & d["ano"].isin(R.ANOS) & (d["produto"] != "Total")]
    return d


def _fatos_pam(ponto: str | None, culturas: list[str], tema: str = "pam") -> list[dict]:
    ibge = _ibge(ponto)
    o = "IBGE/PAM (SIDRA 1612) via data/processed/pam_ce.parquet, médias de 2021 a 2023"
    if not ibge:
        return [_sem_local(tema, "o que o município planta")] if not ponto else [_f(tema, "PAM", "Para o seu município ainda não temos dado de produção do IBGE.", o, lacuna=True, prio=1)]
    try:
        d = _pam(ibge)
    except Exception:  # noqa: BLE001
        return []
    a = d[d["variavel"] == "area_colhida_ha"].groupby("produto")["valor"].mean().dropna()
    a = a[a > 0].sort_values(ascending=False)
    out = []
    if len(a):
        top = a.head(4)
        out.append(_f(tema, "o que o município planta", "Nos dados do IBGE (2021 a 2023), o que mais ocupa área no seu município é: "
                      + "; ".join(f"{p.split(' (')[0].lower()} ({FT.milhar(v)} hectares)" for p, v in top.items()) + ". É o que já se colhe, não uma recomendação.", o, prio=1,
                      qual="Nos dados do IBGE, o que mais ocupa área no seu município é, nessa ordem: " + ", ".join(p.split(' (')[0].lower() for p in top.index) + ". É o que já se colhe, não uma recomendação."))
    else:
        out.append(_f(tema, "o que o município planta", "Não achei dado de área colhida do IBGE para o seu município.", o, lacuna=True, prio=1))
    from src.culturas import renda as R
    for cid in culturas[:2]:
        prod = R.PAM_PRODUTO.get(cid)
        if prod:
            ren = d[(d["variavel"] == "rendimento_medio") & (d["produto"] == prod)]["valor"].dropna()
            ar = a.get(prod)
            if len(ren):
                out.append(_f(tema, f"rendimento de {cid}", f"Nos dados do IBGE (2021 a 2023), {_art(cid)} rendeu em média {FT.milhar(ren.mean())} kg por hectare no seu município"
                              + (f", em cerca de {FT.milhar(ar)} hectares" if ar else "") + ". É o que já aconteceu, não é previsão do que você vai colher.", o, prio=2,
                              qual="O IBGE tem o rendimento " + _art(cid, "do") + " no seu município, mas só mostro o número se você pedir. É o que já aconteceu, não é previsão do que você vai colher."))
            elif prod and ar is None:
                out.append(_f(tema, f"{cid} no município", f"No IBGE, {_art(cid)} não aparece com área colhida no seu município nesses anos.", o, lacuna=True, prio=2))
    return out


def _fatos_renda(ponto: str | None, culturas: list[str]) -> list[dict]:
    """O que existe de dinheiro: receita BRUTA por hectare (IBGE). Nunca lucro."""
    ibge = _ibge(ponto)
    o = "src.culturas.renda.renda_com_lacunas (IBGE/PAM, receita bruta 2021-2023)"
    if not ponto:
        return []
    if not ibge:
        return [_f("renda", "receita bruta", "Ainda não temos dado de venda do IBGE para o seu município.", o, lacuna=True, prio=2)]
    from src.culturas import renda as R
    ids = culturas[:3] or ["milho", "feijao_caupi", "mandioca"]
    try:
        r = R.renda_com_lacunas(ibge, ids)
    except Exception:  # noqa: BLE001
        return []
    com = [f"{_nome(c)} R$ {FT.milhar(r[c]['receita_bruta_r_ha'])}" for c in ids if r.get(c) and r[c].get("receita_bruta_r_ha")]
    out = []
    if com:
        out.append(_f("renda", "receita bruta", "Nos dados do IBGE, a venda bruta por hectare no seu município foi: " + "; ".join(com) + " (média de 2021 a 2023). "
                      "Isso não é lucro, porque não desconta os custos.", o, prio=2))
    sem = [_nome(c) for c in ids if not (r.get(c) and r[c].get("receita_bruta_r_ha"))]
    if sem:
        out.append(_f("renda", "receita bruta sem dado", f"Ainda não temos dado de venda do IBGE para: {', '.join(sem)}.", o, lacuna=True, prio=3))
    return out


_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _fatos_chuva_atual(ponto: str | None, hoje, pergunta: str) -> list[dict]:
    """Chuva da ÉPOCA ATUAL (mês de hoje) e do ano até agora, comparadas com a média de 2001 em diante, com a série diária do local."""
    if not ponto:
        return [_sem_local("chuva_atual", "a chuva desta época")]
    import pandas as pd
    from src.culturas import calendario_plantio as CP
    o = "src.culturas.calendario_plantio._clima_do_ponto (chuva diária NASA POWER do local, 2001 em diante)"
    df = CP._clima_do_ponto(ponto)
    if df is None or not len(df):
        return [_f("chuva_atual", "chuva do mês", "Ainda não temos a chuva diária do seu local.", o, lacuna=True, prio=1)]
    d = df.copy()
    d["data"] = pd.to_datetime(d["data"])
    fim = d["data"].max()
    n = corrigir_grafia(_norm(pergunta))
    m = next((i + 1 for i, nm in enumerate(["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]) if nm in n), None)
    out = []
    if re.search(r"esse ano|este ano|choveu", n) and not m:
        ano = fim.year
        ate = fim.day_of_year
        atual = d[(d["data"].dt.year == ano)]["chuva_mm"].sum()
        hist = d[(d["data"].dt.year < ano) & (d["data"].dt.day_of_year <= ate)].groupby(d["data"].dt.year)["chuva_mm"].sum()
        if len(hist) >= 5:
            med = hist.mean()
            rel = "perto da média" if abs(atual - med) <= 0.1 * med else ("acima da média" if atual > med else "abaixo da média")
            out.append(_f("chuva_atual", "chuva do ano", f"Em {ano}, até {fim.day}/{fim.month}, choveu {FT.milhar(atual)} mm no seu local, {rel} do mesmo período nos anos anteriores ({FT.milhar(med)} mm). "
                          "A chuva vem de uma área grande: na sua roça pode ter sido diferente.", o, prio=1,
                          qual=f"Em {ano}, até agora, choveu {rel} do mesmo período nos anos anteriores. A chuva vem de uma área grande: na sua roça pode ter sido diferente."))
        return out or [_f("chuva_atual", "chuva do ano", "Não deu para comparar a chuva deste ano com os anos anteriores.", o, lacuna=True, prio=1)]
    mes = m or hoje.month
    ds = d[d["data"].dt.month == mes]
    por_ano = ds.groupby(ds["data"].dt.year)["chuva_mm"].sum()
    dias = ds.assign(c=ds["chuva_mm"] >= 1).groupby(ds["data"].dt.year)["c"].sum()
    if len(por_ano) >= 5:
        qual = "o mês mais chuvoso" if por_ano.mean() >= d.groupby([d["data"].dt.year, d["data"].dt.month])["chuva_mm"].sum().groupby(level=1).mean().max() else None
        mx_mes = d.groupby([d["data"].dt.year, d["data"].dt.month])["chuva_mm"].sum().groupby(level=1).mean().max()
        nivel = "é um dos meses mais chuvosos" if por_ano.mean() >= 0.6 * mx_mes else "chove pouco" if por_ano.mean() >= 0.15 * mx_mes else "quase não chove"
        out.append(_f("chuva_atual", "chuva do mês", f"Em {_MESES[mes - 1]}, em média, chove {FT.milhar(por_ano.mean())} mm no seu local, em {'cerca de 1 dia' if round(dias.mean()) == 1 else 'uns ' + FT.br(dias.mean(), 0) + ' dias'} com chuva"
                      + (", e é o mês mais chuvoso do ano." if qual else ".") + " A chuva da sua roça pode ser diferente.", o, prio=1,
                      qual=f"Em {_MESES[mes - 1]}, no seu local, {nivel}. A chuva da sua roça pode ser diferente."))
        ult = por_ano.index.max()
        if ult == fim.year and mes == hoje.month and m is None and len(por_ano) > 1:
            ant = por_ano.drop(ult)
            parcial = ds[ds["data"].dt.year == ult]
            if len(parcial) and fim.month == mes and len(ant) >= 5:
                ref = ds[(ds["data"].dt.year < ult) & (ds["data"].dt.day <= fim.day)].groupby(ds["data"].dt.year)["chuva_mm"].sum().mean()
                at = parcial["chuva_mm"].sum()
                rel = "perto da média" if abs(at - ref) <= 0.1 * max(ref, 1) else ("acima da média" if at > ref else "abaixo da média")
                out.append(_f("chuva_atual", "chuva do mês até agora", f"Neste mês, até o dia {fim.day}, choveu {FT.milhar(at)} mm, {rel} do mesmo período nos outros anos ({FT.milhar(ref)} mm).", o, prio=1,
                              qual=f"Neste mês, até agora, choveu {rel} do mesmo período nos outros anos."))
    return out


def _fatos_plantar_agora(ponto: str | None, hoje) -> list[dict]:
    """O que o zoneamento (ZARC) permite plantar no mês de hoje e o que o clima do local aceita; sem preferir uma."""
    if not ponto:
        return [_sem_local("plantar_agora", "o que dá para plantar nesta época")]
    from src.app import filtros as F
    from src.culturas import avaliar_sequencia as AS
    from src.culturas import zarc as Z
    o = "src.culturas.zarc.janela (ZARC, risco " + str(F.RISCO_ZARC) + "%) + src.culturas.avaliar_sequencia.avaliacao_local"
    mes = hoje.month
    try:
        geo = Z.geocodigo_do_ponto(ponto)
        av = AS.avaliacao_local(ponto)["culturas"]
    except Exception:  # noqa: BLE001
        return [_f("plantar_agora", "plantar agora", "Não consegui olhar agora o que dá para plantar nesta época.", o, lacuna=True, prio=1)]
    pode, sem_zarc = [], []
    for cid in _nomes():
        if (av.get(cid) or {}).get("estado") != "viavel":
            continue
        j = Z.janela(geo, cid, F.RISCO_ZARC, "qualquer")
        perm = j.get("permitido")
        if perm is None or len(perm) != 36 or j.get("aproximada"):
            sem_zarc.append(cid)
        elif any(perm[(mes - 1) * 3:(mes - 1) * 3 + 3]):
            pode.append(cid)
    out = []
    if pode:
        out.append(_f("plantar_agora", "plantar agora", f"Em {_MESES[mes - 1]}, o zoneamento do Ministério da Agricultura permite plantar, no seu local: {_lista(pode[:6])}. "
                      "O zoneamento não considera pragas e doenças, e os dados não mostram qual é melhor.", o, prio=1))
    else:
        out.append(_f("plantar_agora", "plantar agora", f"Em {_MESES[mes - 1]}, o zoneamento do Ministério da Agricultura não permite o plantio de nenhuma das culturas do Sulco no seu local.", o, prio=1))
    if sem_zarc:
        out.append(_f("plantar_agora", "sem zoneamento", f"Para {_lista(sem_zarc[:5])} não há zoneamento do governo para o seu município; por isso não dá para dizer o mês.", o, lacuna=True, prio=2))
    return out


def _fatos_rotacao_par(a: str, b: str) -> list[dict]:
    from src.culturas import matriz_rotacao as MR
    o = "data/culturas/matriz_rotacao.csv via src.culturas.matriz_rotacao.consulta (evidência do acervo)"
    try:
        c = MR.consulta(a, b)
    except Exception:  # noqa: BLE001
        return [_f("rotacao_par", "rotação", f"Não consegui olhar {_art(b)} depois {_art(a, 'do')} agora.", o, lacuna=True, prio=1)]
    par = f"{_art(b)} depois {_art(a, 'do')}"
    ev = c.get("evidencias") or []
    crit = sorted({e.get("criterio") for e in ev if e.get("criterio")})
    nomes_c = {"sanidade": "doenças e pragas", "nitrogenio": "nitrogênio", "familia_graminea": "a família da planta", "agua": "água", "solo": "solo",
               "palha": "palha", "alelopatia": "efeito de uma planta sobre a outra"}
    cs = ", ".join(nomes_c.get(x, x.replace("_", " ")) for x in crit[:3])
    g = c["grau"]
    regiao = " É recomendação técnica de outras regiões, não prova do seu local." if (c.get("tipo_evidencia_mais_forte") == "recomendacao_tecnica") else " Vem de estudo de outra região, não do seu local."
    if c.get("divergente"):
        txt = f"Os materiais consultados divergem sobre {par}: um lado é favorável e outro traz um ponto de atenção ({cs}). Por isso o Sulco não dá nota a esse par."
    elif g == "favoravel":
        txt = f"Pelo material consultado, {par} tem evidência favorável (assunto: {cs or 'rotação'})." + regiao
    elif g == "desfavoravel":
        txt = f"Pelo material consultado, {par} tem um ponto de atenção (assunto: {cs or 'rotação'})." + regiao
    elif g == "neutro":
        txt = f"Pelo material consultado, {par} aparece como neutro: sem ganho nem perda claros (assunto: {cs or 'rotação'})." + regiao
    else:
        txt = f"No material consultado, não achei nada sobre {par}. Isso é falta de dado, não é sinal de que é ruim."
    return [_f("rotacao_par", f"rotação {a}-{b}", txt, o, lacuna=g not in ("favoravel", "desfavoravel", "neutro") or bool(c.get("divergente")), prio=1)]


def _fatos_depois_de(cid: str, ponto: str | None) -> list[dict]:
    from src.culturas import calendario_plantio as CP
    o = "src.culturas.calendario_plantio.proximas_padrao (matriz de rotação + viabilidade do local)"
    try:
        pr = CP.proximas_padrao(cid, CP.Contexto(ponto)) if ponto else None
        if pr is None:
            from src.culturas import matriz_rotacao as MR
            graus = {}
            for b in _tabela():
                if b != cid:
                    try:
                        cc = MR.consulta(cid, b)
                        graus[b] = {"grau": cc["grau"], "divergente": bool(cc["divergente"]), "tipo": cc.get("tipo_evidencia_mais_forte")}
                    except KeyError:
                        pass
            pr = CP.organizar_proximas(cid, graus, None)
    except Exception:  # noqa: BLE001
        return [_f("rotacao_par", "depois de", f"Não consegui olhar o que vem depois {_art(cid, 'do')} agora.", o, lacuna=True, prio=1)]
    out = []
    if pr["favoraveis"]:
        txt = f"Depois {_art(cid, 'do')}, o material consultado mostra evidência favorável para: {_lista(pr['favoraveis'][:5])}."
        if pr.get("empate_entre_favoraveis"):
            txt += " Os dados não mostram qual delas é melhor."
        out.append(_f("rotacao_par", f"depois de {cid}", txt, o, prio=1))
    try:
        from src.culturas import matriz_rotacao as MR
        div = [b for b in pr["sem_dado"] if MR.consulta(cid, b)["divergente"]]
        neu = pr.get("neutras") or []
    except Exception:  # noqa: BLE001
        div, neu = [], []
    if neu:
        out.append(_f("rotacao_par", f"neutras depois de {cid}", f"Depois {_art(cid, 'do')}, aparecem como neutras, sem ganho nem perda claros: {_lista(neu[:4])}.", o, prio=2))
    if div:
        out.append(_f("rotacao_par", f"divergentes depois de {cid}", f"Depois {_art(cid, 'do')}, os materiais divergem sobre: {_lista(div[:4])} (um lado favorável e outro com ponto de atenção).", o, prio=2))
    if pr["desfavoraveis"]:
        out.append(_f("rotacao_par", f"cuidado depois de {cid}", f"Depois {_art(cid, 'do')}, tem ponto de atenção para: {_lista(pr['desfavoraveis'][:4])}.", o, prio=2))
    if not (pr["favoraveis"] or pr["desfavoraveis"] or neu or div):
        out.append(_f("rotacao_par", f"depois de {cid}", f"No material consultado, não achei evidência do que plantar depois {_art(cid, 'do')}; isso é falta de dado.", o, lacuna=True, prio=1))
    if ponto and pr.get("inviaveis_no_local"):
        out.append(_f("rotacao_par", "fora do clima", f"No seu local, ficam de fora pelo clima: {_lista(pr['inviaveis_no_local'][:5])}.", o, prio=3))
    return out


def _fatos_consorcio(culturas: list[str]) -> list[dict]:
    from src.culturas import consorcio as CO
    o = "data/culturas/ler_staging.csv via src.culturas.consorcio (estudos publicados no semiárido do Nordeste, LER)"
    out = []
    if len(culturas) >= 2:
        a, b = culturas[0], culturas[1]
        try:
            r = CO.resumo_par(a, b)
        except Exception:  # noqa: BLE001
            r = None
        if r:
            lo, hi = FT.br(r["ler_min"], 2), FT.br(r["ler_max"], 2)
            faixa = lo if lo == hi else f"{lo} a {hi}"
            out.append(_f("consorcio", f"consórcio {a}-{b}", f"Em {r['n_estudos']} {'estudo' if r['n_estudos'] == 1 else 'estudos'} no semiárido do Nordeste, {_art(a)} junto com {_art(b)} deu um índice de uso da terra (LER) de {faixa}. "
                          "Acima de 1, a terra rendeu mais junta do que separada. É de outro lugar: não é do seu terreno e não prevê ganho.", o, prio=1,
                          qual=(f"Nos estudos feitos no semiárido do Nordeste, {_art(a)} junto com {_art(b)} aproveitou a terra mais do que plantar separado. " if r["ler_min"] > 1 else
                                f"Nos estudos feitos no semiárido do Nordeste, {_art(a)} junto com {_art(b)} nem sempre aproveitou a terra mais do que plantar separado. ")
                          + "É de outro lugar e outro ano: não é do seu terreno e não prevê ganho."))
        else:
            out.append(_f("consorcio", f"consórcio {a}-{b}", f"Não achei estudo publicado no semiárido de {_art(a)} junto com {_art(b)}. Falta de estudo é falta de dado, não é sinal ruim.", o, lacuna=True, prio=1))
        return out
    pares = CO.pares_com_respaldo()
    if culturas:
        c = culturas[0]
        parc = [y if x == c else x for x, y in pares if c in (x, y)]
        if parc:
            out.append(_f("consorcio", f"consórcio de {c}", f"Com estudo publicado no semiárido, {_art(c)} aparece junto com: {_lista(parc[:5])}. Pergunte de um par que eu mostro os números.", o, prio=1))
        else:
            out.append(_f("consorcio", f"consórcio de {c}", f"Não achei estudo publicado no semiárido de consórcio com {_art(c)}. Falta de estudo é falta de dado, não é sinal ruim.", o, lacuna=True, prio=1))
    else:
        out.append(_f("consorcio", "consórcio", "Consórcio é plantar duas culturas juntas na mesma área. O Sulco só tem estudos publicados do semiárido para alguns pares, como milho com feijão-caupi ou milho com sorgo.", o, prio=1))
    return out


def _fatos_por_que_nao(cid: str, ponto: str | None, est: dict) -> list[dict]:
    out = []
    if cid in (est.get("proibidas") or []):
        out.append(_f("por_que_nao", "cultura que você não quer", f"Você disse que não quer {_nome(cid)}, por isso ela fica de fora.", "estado da conversa (regras duras)", prio=1))
    out += _fatos_viabilidade(cid, ponto, "por_que_nao")
    if ponto and not any(f["lacuna"] or "não ficou" in f["texto_simples"] for f in out):
        out.append(_f("por_que_nao", "o que decide", "O Sulco mostra só três caminhos (o que você faz hoje e duas alternativas). Uma cultura que dá certo no clima pode ficar de fora porque outras "
                      "ficaram na frente no que você escolheu, ou porque os dados não separam uma da outra.", "src.culturas.avaliar_sequencia (viabilidade + pareto)", prio=2))
    return out


def _fatos_listas_tabela(tema: str) -> list[dict]:
    """Adubação verde (nitrogênio) e palha: ranking da tabela de culturas, com os mesmos números e a unidade da tabela."""
    tab = _tabela()
    o = "data/culturas/tabela_culturas.csv (valores lidos de trabalhos do acervo)"
    if tema == "adubacao_verde":
        chave, quem, un = "n_fixado_kg_ha", "mais deixam nitrogênio na terra", "kg de nitrogênio por hectare"
    else:
        chave, quem, un = "palha_ms_kg_ha", "mais deixam palha", "kg de palha seca por hectare"
    itens = sorted(((cid, _atr(cid, chave)) for cid in tab if _atr(cid, chave)), key=lambda x: -x[1])
    if not itens:
        return [_f(tema, "ranking da tabela", "Ainda não temos esse dado na tabela de culturas.", o, lacuna=True, prio=1)]
    return [_f(tema, "ranking da tabela", f"Entre as culturas do Sulco, as que {quem}, pela tabela, são: " + "; ".join(f"{_nome(i)} ({FT.milhar(v)} {un})" for i, v in itens[:3])
               + ". São valores de trabalhos de outras regiões: variam com o solo e o manejo.", o, prio=1,
               qual=f"Entre as culturas do Sulco, as que {quem}, pela tabela, são: " + ", ".join(_nome(i) for i, _ in itens[:3]) + ". São valores de trabalhos de outras regiões: variam com o solo e o manejo.")]


def _tr(t: dict) -> dict:
    return {"arquivo": t.get("arquivo", ""), "pagina": t.get("pagina"), "texto": t.get("texto", "")}


def _glossario(pergunta: str) -> list[dict]:
    out = []
    try:
        tr = _sulco.buscar(pergunta)["trechos"]
    except Exception:  # noqa: BLE001
        tr = []
    for t in tr[:2]:
        if t.get("texto_simples") and ("glossário" in t.get("arquivo", "") or "limites" in t.get("arquivo", "") or "como o Sulco" in t.get("arquivo", "")):
            out.append({**_f("glossario", "glossário do Sulco", t["texto_simples"], t.get("arquivo") or "sobre o Sulco", prio=1), "_trecho": _tr(t)})
    return out


def _fatos_sobre_sulco(pergunta: str, tema: str) -> list[dict]:
    out = []
    try:
        tr = _sulco.buscar(pergunta)["trechos"]
    except Exception:  # noqa: BLE001
        tr = []
    for t in tr[:3]:
        if t.get("texto_simples"):
            out.append({**_f(tema, "sobre o Sulco", t["texto_simples"], t.get("arquivo") or "sobre o Sulco", prio=1), "_trecho": _tr(t)})
    return out


# ---------- lacunas honestas
_LACUNAS = {
    "clima_futuro": ("a chuva que vem", "O Sulco não prevê chuva nem o tempo: ele só mostra o que já aconteceu no seu local."),
    "preco": ("o preço de venda", "Ainda não temos dado de preço de venda dos produtos."),
    "custo": ("o custo de plantar", "Ainda não temos dado de custo de plantio, de adubo, de mão de obra nem de financiamento."),
    "semente": ("a semente", "Ainda não temos dado de semente: qual variedade, quanto custa nem onde comprar."),
    "venda": ("a venda", "Ainda não temos dado de comprador, de mercado nem de preço de venda."),
    "lucro": ("o lucro", "O Sulco não calcula lucro: não tem dado de preço nem de custo."),
    "produtividade": ("quanto vai colher", "O Sulco não prevê quanto você vai colher."),
    "pragas": ("pragas e doenças", "Ainda não temos dado de praga e doença do seu local; o zoneamento do governo também não considera isso."),
    "adubo": ("adubo", "Ainda não temos dado de adubo: qual, quanto nem quando usar."),
    "irrigacao": ("irrigação", "Ainda não temos dado de irrigação: o Sulco olha o plantio só na chuva e não sabe quanta água você tem."),
    "manejo": ("o jeito de plantar", "Ainda não temos dado do jeito de plantar (espaçamento, covas, tratos) no Sulco."),
}
_ORIGEM_LAC = "limite do projeto: dado não existe no Sulco (docs/27, docs/15)"


def _fato_lacuna(tema: str) -> dict:
    o, txt = _LACUNAS[tema]
    return _f(tema, f"sem dado: {o}", txt, _ORIGEM_LAC, lacuna=True, prio=0)


def _fatos_sanidade(cid: str) -> list[dict]:
    """O pouco que há sobre doença: rotação com sanidade favorável no acervo (recomendação técnica, outra região)."""
    from src.culturas import matriz_rotacao as MR
    try:
        m = MR.carregar()
    except Exception:  # noqa: BLE001
        return []
    outros = sorted({(a if b == cid else b) for (a, b), ev in m.items() if cid in (a, b) and a != b and any(e.get("criterio") == "sanidade" and e.get("grau") == "favoravel" for e in ev)})
    if not outros:
        return []
    return [_f("pragas", f"sanidade de {cid}", f"O pouco que temos sobre doença {_art(cid, 'do')}: no material consultado, alternar com {_lista(outros[:4])} aparece como ajuda para quebrar doença. "
               "É recomendação técnica de outras regiões.", "data/culturas/matriz_rotacao.csv (critério sanidade)", prio=2)]


def _fatos_forragem(ponto: str | None) -> list[dict]:
    from src.culturas import forragem as FG
    out = [_f("forragem", "valor forrageiro", "Ainda não temos o valor de comida para os animais (quanto de massa dão) da palma, do sorgo e do milheto: nos PDFs só há gráfico sem números, e o Sulco não estima.",
              "src.culturas.forragem.AVISO (lacuna C-forragem)", lacuna=True, prio=0)]
    if ponto:
        for cid in ("palma_forrageira", "sorgo", "milheto"):
            out += _fatos_viabilidade(cid, ponto, "forragem")[:1]
    return out


# ------------------------------------------------------------------------------------------------ RAG: trecho cru -> frases simples
_RUIDO = re.compile(r"\bet al\b|https?:|www\.|\bISBN\b|\bISSN\b|\bFig(ura|\.)|\bTabela\b|\bQuadro\b|\bpp?\.\s*\d|\(\d{4}\)|\b(19|20)\d{2}[a-z]?\b.{0,3}\)|©|\bDOI\b|\bEmbrapa [A-Z]\w+|\bAutor|"
                    r"\bBrasília\b|\bResumo\b|\bAbstract\b|\bSumário\b|\bCapítulo\b|\bEditor|\bOrganizador|\bPrefácio|\bAgradecimentos")
_NOME_PROPRIO = re.compile(r"\b[A-ZÀ-Ú][a-zà-ú]{2,}\s+(?:(?:de|da|do|dos|das)\s+)?[A-ZÀ-Ú][a-zà-ú]{2,}(?:\s+(?:(?:de|da|do|dos|das)\s+)?[A-ZÀ-Ú][a-zà-ú]{2,})+")
MAX_PALAVRAS_FRASE = 26
MAX_PALAVRAS_TRECHO = 45
_CABECALHO = re.compile(r"^[A-ZÀ-Ú][\wà-ú]+(?: [A-ZÀ-Ú][\wà-ú]+)+ [-–] |^[A-ZÀ-Ú][\wà-ú]+ [A-ZÀ-Ú][\wà-ú]+ |\b\d+\s?g\.? ?i\. ?a|\d\.$|/\d+\.$")


def frases_simples(texto: str, pergunta: str, max_frases: int = 2) -> list[str]:
    """Trecho de PDF -> até `max_frases` frases COMPLETAS que mais casam com a pergunta, sem autor, citação, tabela nem cabeçalho. Só seleciona e limpa:
    nunca acrescenta palavra. Vazio = nada que sirva."""
    from .chat import limpar_trecho_pdf, _radicais
    base = limpar_trecho_pdf(texto, max_frases=8, max_chars=1400)
    if not base:
        return []
    q = _radicais(pergunta)
    cand = []
    for i, fr in enumerate(re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú])", base)):
        fr = fr.strip()
        pal = fr.split()
        if not (6 <= len(pal) <= MAX_PALAVRAS_FRASE) or not fr.endswith((".", "!")) or fr[0].islower():
            continue
        if _RUIDO.search(fr) or _NOME_PROPRIO.search(fr) or "?" in fr or fr.endswith(":") or _CABECALHO.search(fr) or fr.count("(") != fr.count(")"):
            continue
        if sum(ch.isdigit() for ch in fr) > 0.12 * len(fr) or sum(ch.isupper() for ch in fr) > 0.2 * len(fr):
            continue
        hit = len(q & _radicais(fr))
        cand.append((hit, -i, fr))
    cand = [c for c in cand if c[0] >= (1 if len(q) <= 2 else 2)]
    cand.sort(reverse=True)
    escolhidas = sorted(cand[:max_frases], key=lambda c: -c[1])
    out, pal = [], 0
    for c in escolhidas:
        pal += len(c[2].split())
        if out and pal > MAX_PALAVRAS_TRECHO:
            break
        out.append(c[2])
    return out


def _fatos_rag(pergunta: str, buscar_fn=None, max_trechos: int = 2) -> list[dict]:
    from . import chat as CH
    try:
        r = (buscar_fn or CH._buscar_padrao)(pergunta)
    except Exception:  # noqa: BLE001
        r = None
    if not isinstance(r, dict) or r.get("sem_evidencia") or not r.get("trechos"):
        return []
    out = []
    for t in CH.trechos_que_respondem(CH._limpar_trechos(r["trechos"]), pergunta):
        if CH._sulco.e_sobre_o_sulco(t.get("arquivo", "")):
            continue
        fr = frases_simples(t.get("texto", ""), pergunta)
        if not fr:
            continue
        fonte = CH.fonte_curta(t.get("arquivo", ""))
        txt = " ".join(fr)
        pre = (f"Pelo material {'da ' + fonte[2:] if fonte.startswith('a ') else 'do ' + fonte[2:] if fonte.startswith('o ') else 'da ' + fonte}: "
               if fonte else "No material que o Sulco consultou: ")
        out.append({**_f("acervo", f"acervo: {CH._nome_documento(t.get('arquivo', ''))[:60]}", pre + txt, f"{t.get('arquivo', '')}, p. {t.get('pagina')}", prio=2, texto=txt),
                    "_trecho": _tr(t)})
        if len(out) >= max_trechos:
            break
    return out


# ------------------------------------------------------------------------------------------------ FICHA COMPLETA + busca por similaridade (BM25)
# A ficha reúne, SEM lista fixa de perguntas, todos os fatos curtos que o código consegue montar dos dados do local, das 16 culturas, do município (IBGE),
# da rotação, do consórcio, do glossário e dos limites. Cada fato leva TAGS/sinônimos (só para achar; nunca aparecem na resposta). A pergunta é comparada
# com a ficha por BM25 (o mesmo do acervo, `rag.busca`), de modo que assuntos que nenhuma regra de tema prevê ainda achem fatos.
LIMIAR_BM25 = 3.5          # medido na bateria (docs/21_resultados_fases/CONVERSA_LIVRE.md): abaixo disso a pergunta é de fora do Sulco
LIMIAR_COBERTURA = 0.30    # fração (ponderada por idf) das palavras da pergunta que o fato cobre
K_FICHA = 8
_TAGS = {
    "diagnostico": "clima chuva estação chuvosa inverno veranico seco terra descoberta solo nu estresse planta sofre épocas verão satélite tendência anos",
    "previsao": "verde satélite vegetação futuro próximas semanas previsão ndvi melhorar piorar normal",
    "previsao_limites": "previsão limite futuro semanas verde", "modelo_skill": "modelo acerta confiável métrica teste previsão erro",
    "solo": "solo terra textura argila areia arenoso ph acidez carbono fértil tipo de terra", "risco": "erosão enxurrada terra levar escoamento declive chuva forte",
    "extremos": "calor quente dias quentes chuva forte temporal tempestade extremos", "eto": "água evaporação evapotranspiração seca falta de água calor balanço",
    "renda": "dinheiro venda receita renda ibge faturamento", "limites": "limite dados satélite fonte resolução confiável enxerga origem",
    "clima": "chuva chover mês", "zarc": "zoneamento ministério época plantio plantar quando mês janela", "ciclo": "dias colher colheita demora ciclo fase quanto tempo",
    "cultura_clima": "chuva calor temperatura seca aguenta resiste faixa frio tolera água precisa", "viabilidade": "dá certo aqui plantar serve local clima",
    "rotacao_par": "rotação depois antes sucessão sequência evidência material consultado", "consorcio": "junto consórcio misturar mesma área ler plantar com",
    "pam": "município produz planta área colhida ibge rendimento produção lavoura hectares", "glossario": "o que é significa quer dizer termo",
    "clima_mes": "mês chuva média calor temperatura máxima mínima quente frio mais quente mais frio verão inverno seca quanto chove cai", "forragem": "gado animais pasto ração forragem palma",
    "por_que_nao": "por que não aparece sugeriu fora", "sanidade": "doença praga rotação sanidade",
}
_STOP_FICHA = {"comprar", "conta", "novo", "nova", "fica", "ficar", "faz", "fazer", "ajuda", "serve", "tem", "ter", "aqui", "vocês", "voces", "informacoes", "rapido", "quem", "melhor", "como","quer", "voce", "gostaria", "saber", "queria", "tenho", "uma", "duvida", "diga", "fale", "conte", "explique", "favor"}


def _tag(f: dict) -> str:
    return _TAGS.get(f["tema"], "") + " " + f["rotulo"] + " " + (f.get("cultura") and _nome(f["cultura"]) or "")


@lru_cache(maxsize=4)
def _clima_completo(ponto: str):
    import pandas as pd
    from src.culturas import calendario_plantio as CP
    base = CP.RAIZ / "data/processed"
    for nome in ("clima_diario_atual.parquet", "clima_diario.parquet"):
        pq = base / nome
        if pq.exists():
            d = pd.read_parquet(pq, columns=["ponto_id", "data", "chuva_mm", "tmax_c", "tmin_c"], filters=[("ponto_id", "==", ponto)])
            if len(d):
                d["data"] = pd.to_datetime(d["data"])
                return d
    return None


def _fatos_meses(ponto: str) -> list[dict]:
    """Um fato por mês: chuva média, dias com chuva, temperatura máxima e mínima médias (série diária do local)."""
    d = _clima_completo(ponto)
    if d is None:
        return []
    o = "data/processed/clima_diario_atual.parquet (NASA POWER, média por mês de 2001 em diante; célula de cerca de 50 km)"
    out = []
    anos = d["data"].dt.year.nunique()
    for m in range(1, 13):
        x = d[d["data"].dt.month == m]
        if not len(x):
            continue
        chuva = x.groupby(x["data"].dt.year)["chuva_mm"].sum().mean()
        dias = (x["chuva_mm"] >= 1).groupby(x["data"].dt.year).sum().mean()
        txt = f"Em {_MESES[m - 1]}, no seu local, chove em média {FT.milhar(chuva)} mm, em {'cerca de 1 dia' if round(dias) == 1 else 'uns ' + FT.br(dias, 0) + ' dias'} com chuva"
        if x["tmax_c"].notna().any():
            txt += f"; a máxima do dia fica perto de {FT.br(x['tmax_c'].mean(), 0)} graus e a mínima perto de {FT.br(x['tmin_c'].mean(), 0)} graus"
        out.append((_f("clima_mes", f"clima de {_MESES[m - 1]}", txt + f". Média de {anos} anos; a roça pode ser diferente.", o, prio=2), chuva))
    mx = max(c for _, c in out) if out else 1
    fin = []
    for f, c in out:
        f["qual"] = (f"Em {f['rotulo'][9:]}, no seu local, " + ("é um dos meses mais chuvosos" if c >= 0.6 * mx else "chove pouco" if c >= 0.15 * mx else "quase não chove") + ". A roça pode ser diferente.")
        fin.append(f)
    return fin


def _fatos_pam_produtos(ponto: str | None) -> list[dict]:
    ibge = _ibge(ponto)
    if not ibge:
        return []
    try:
        d = _pam(ibge)
    except Exception:  # noqa: BLE001
        return []
    o = "IBGE/PAM (SIDRA 1612) via data/processed/pam_ce.parquet, médias de 2021 a 2023"
    a = d[d["variavel"] == "area_colhida_ha"].groupby("produto")["valor"].mean().dropna()
    r = d[d["variavel"] == "rendimento_medio"].groupby("produto")["valor"].mean().dropna()
    out = []
    for prod, ar in a[a > 0].sort_values(ascending=False).head(8).items():
        nm = prod.split(" (")[0].lower()
        txt = f"No IBGE, {nm} ocupa em média {FT.milhar(ar)} hectares no seu município (2021 a 2023)"
        if prod in r.index and r[prod] > 0:
            txt += f" e rendeu em média {FT.milhar(r[prod])} kg por hectare"
        out.append(_f("pam", f"IBGE: {nm}", txt + ". É o que já se colheu, não uma previsão.", o, prio=2,
                      qual=f"No IBGE, {nm} está entre as culturas que mais ocupam área no seu município. É o que já se colheu, não uma previsão." if len(out) < 3 else None))
    return out


@lru_cache(maxsize=4)
def _ficha(ponto: str | None) -> tuple:
    """Todos os fatos candidatos (tupla de dicts) do local `ponto` (ou só os que não dependem do local, se None)."""
    fs: list[dict] = []
    if ponto:
        try:
            fs += [{**f} for f in _folha_local(ponto)["fatos"] if f.get("texto_simples") and not f["lacuna"] and f["tema"] not in ("caminhos", "janela")]
        except Exception:  # noqa: BLE001
            pass
        for fn in (_fatos_meses, _fatos_pam_produtos):
            try:
                fs += fn(ponto)
            except Exception:  # noqa: BLE001
                pass
    for cid in _nomes():
        extra = []
        for fn in (_fatos_ciclo, _fatos_faixas, _fatos_sanidade):
            try:
                extra += fn(cid)
            except Exception:  # noqa: BLE001
                pass
        if ponto:
            for fn in (lambda c: _fatos_viabilidade(c, ponto), lambda c: _fatos_zarc(c, ponto), lambda c: _fatos_solo_cultura(c, ponto), lambda c: _fatos_janela(c, ponto)):
                try:
                    extra += fn(cid)
                except Exception:  # noqa: BLE001
                    pass
        for f in extra:
            f["cultura"] = cid
        fs += extra
    try:
        from src.culturas import consorcio as CO
        for a, b in CO.pares_com_respaldo():
            fs += [{**f, "cultura": a} for f in _fatos_consorcio([a, b])]
        from src.culturas import matriz_rotacao as MR
        for (a, b), ev in MR.carregar().items():
            if a != b and ev:
                fs += [{**f, "cultura": b} for f in _fatos_rotacao_par(a, b) if not f["lacuna"]]
    except Exception:  # noqa: BLE001
        pass
    for tema in ("preco", "custo", "semente", "venda", "lucro", "produtividade", "pragas", "adubo", "irrigacao", "manejo", "clima_futuro"):
        f = _fato_lacuna(tema)
        f["tags_extra"] = {"preco": "preço cotação quanto custa vale", "custo": "custo gastar financiamento crédito seguro", "semente": "semente variedade cultivar comprar muda",
                           "venda": "vender venda comprador mercado feira cooperativa", "lucro": "lucro dinheiro ganhar compensa vale a pena",
                           "produtividade": "sacas colher produtividade quanto produz", "pragas": "praga doença lagarta fungo inseto veneno",
                           "adubo": "adubo adubação esterco fertilizante calcário", "irrigacao": "irrigar irrigação poço açude regar", "manejo": "espaçamento covas capina poda armazenar",
                           "clima_futuro": "vai chover previsão tempo inverno que vem"}[tema]
        fs.append(f)
    fs.append(_f("sobre_sulco", "o que o Sulco tem", f"O Sulco tem, para o seu município: chuva e temperatura desde 2001, o verde visto do satélite, o zoneamento do governo, ciclo e clima de {len(_nomes())} culturas, "
                 "solo estimado, o que o município colhe (IBGE) e estudos de rotação e consórcio. Não tem preço, custo nem semente.",
                 "src.llm.conhecimento (inventário das fontes do Sulco)", prio=1))
    fs[-1]["tags_extra"] = "sulco dados quais dados o que você sabe tem informação fontes"
    try:
        for d in _sulco.documentos():
            if d.get("grupo") in ("termo", "limites") and d.get("texto_simples"):
                fs.append({**_f("glossario", "glossário: " + str(d.get("texto", ""))[:40], d["texto_simples"], str(d.get("arquivo")), prio=2),
                           "tags_extra": str(d.get("texto", ""))[:200]})
    except Exception:  # noqa: BLE001
        pass
    seen, out = set(), []
    for f in fs:
        if f["texto_simples"] in seen or trecho_suspeito_f(f["texto_simples"]):
            continue
        seen.add(f["texto_simples"])
        f.setdefault("papel", "livre")
        out.append(f)
    return tuple(out)


def trecho_suspeito_f(t: str) -> bool:
    from .seguranca import trecho_suspeito
    return trecho_suspeito(t)


@lru_cache(maxsize=4)
def _indice(ponto: str | None):
    from src.rag.busca import BM25, tokenizar
    fs = _ficha(ponto)
    docs = [tokenizar(f["texto_simples"] + " " + _tag(f) + " " + f.get("tags_extra", "")) for f in fs]
    return fs, BM25(docs), tokenizar


def buscar_ficha(pergunta: str, ponto: str | None, culturas: list[str] | None = None, k: int = K_FICHA) -> list[tuple[float, dict]]:
    """Top-k fatos da ficha por similaridade (BM25) com a pergunta, com reforço da cultura citada. [(nota, fato)] já acima do LIMIAR_BM25."""
    from src.rag.busca import expandir_consulta
    fs, bm, tok = _indice(ponto)
    n = corrigir_grafia(_norm(pergunta))
    q = [t for t in tok(n + " " + expandir_consulta(pergunta)) if t not in _STOP_FICHA and t not in {tok(w)[0] for w in _STOP_FICHA if tok(w)}]
    sc = bm.scores(q)
    idf_max = max(bm.idf.values()) if bm.idf else 1.0
    total = sum(bm.idf.get(t, idf_max) for t in set(q)) or 1.0
    cult = set(culturas or [])
    out = []
    for i, f in enumerate(fs):
        v = float(sc[i])
        if cult and f.get("cultura"):
            v *= 1.5 if f["cultura"] in cult else 0.4
        if v >= LIMIAR_BM25:
            achou = [t for t in set(q) if t in bm.tf[i]]
            cob = sum(bm.idf[t] for t in achou) / total
            if cob >= LIMIAR_COBERTURA and (len(achou) >= 2 or v >= 7.0):
                out.append((v, f))
    out.sort(key=lambda x: -x[0])
    return out[:k]


# ------------------------------------------------------------------------------------------------ função pública
def _culturas_da_pergunta(pergunta: str, est: dict) -> tuple[list[str], list[str], bool]:
    ext = IT.extrair(pergunta)
    ruim = {a["id"] for a in ext["aproximadas"] if a["termo"] in _LEXICO_SET or a["termo"] in _MESES_N}      # 'janeiro' não é cultura; 'chove' não é 'couve'
    cult = [c for c in dict.fromkeys(list(ext["culturas"]) + list(ext["proibidas"])) if c not in ruim]      # 'por que NÃO sugeriu a palma': a negação é da pergunta, não uma regra
    n = IT._norm(pergunta)
    fora = [x for x in ext["fora_da_lista"] if IT._norm(x) in n]                    # 'chove' não é 'couve': fora da lista só com a palavra escrita certa
    return cult, fora, bool(cult or fora)


def _cortar(fatos: list[dict], teto_tokens: int, max_fatos: int) -> list[dict]:
    out, gasto, vistos = [], 0, set()
    for f in fatos:
        if f["texto_simples"] in vistos:
            continue
        t = FT.tokens_aprox(f["texto_simples"]) + 6
        if gasto + t > teto_tokens or len(out) >= max_fatos:
            continue
        vistos.add(f["texto_simples"])
        out.append(f)
        gasto += t
    return out


def selecionar_fatos(pergunta: str, ponto_id: str | None = None, estado: dict | None = None, *, buscar_fn=None, usar_rag: bool = True, hoje=None,
                     max_fatos: int | None = None, teto_tokens: int | None = None, numeros: bool = True) -> dict:
    """Folha de fatos para uma pergunta livre.

    Devolve {temas, culturas, fatos[{id,tema,rotulo,texto,texto_simples,origem,lacuna,prio,papel}], lacunas[tema], precisa_local, usou_rag}.
    `estado`: estado da conversa (culturas, ponto_id, proibidas). Nunca levanta; sem nada para dizer, devolve UM fato de lacuna ('não achei')."""
    est = estado if isinstance(estado, dict) else {}
    grande = pergunta_grande(pergunta)
    max_fatos = max_fatos or (MAX_FATOS_GRANDE if grande else MAX_FATOS)
    teto_tokens = teto_tokens or (TETO_TOKENS_GRANDE if grande else TETO_TOKENS_LIVRE)
    try:
        from datetime import date
        sel = _selecionar(pergunta, ponto_id, est, buscar_fn, usar_rag, max_fatos, teto_tokens, hoje or date.today(), numeros)
        sel["grande"] = grande
        return sel
    except Exception as e:  # noqa: BLE001 - a conversa nunca quebra por causa do roteador
        f = _f("nada", "sem resposta", SEM_RESPOSTA, f"roteador ({type(e).__name__})", lacuna=True, prio=0)
        f["id"] = "F1"
        return {"temas": [], "culturas": [], "fatos": [f], "lacunas": [], "precisa_local": False, "usou_rag": False, "grande": grande}


def _selecionar(pergunta, ponto_id, est, buscar_fn, usar_rag, max_fatos, teto_tokens, hoje, numeros=True) -> dict:
    temas = detectar_temas(pergunta)
    cult, fora, citou = _culturas_da_pergunta(pergunta, est)
    ponto = ponto_id or est.get("ponto_id")
    cult_conv = [c for c in (est.get("ult_cultura") or est.get("culturas") or []) if c in _nomes()]
    if not cult and not fora and any(t in _USA_CULTURA for t in temas):
        cult = cult_conv[:2]                      # 'e ele aguenta seca?': a cultura que já está na conversa
    cult = cult[:3]
    fatos: list[dict] = []
    lacunas: list[str] = []
    precisa_local = False
    for fo in fora[:1]:
        fatos.append(_f("franqueza", "cultura fora da lista", f"De {fo} ainda não temos dados: essa cultura não está na lista do Sulco. Tenho dados de milho, feijão-caupi, sorgo, mandioca, amendoim e outras.",
                        "data/culturas/tabela_culturas.csv (lista de culturas)", lacuna=True, prio=0))

    def add(fs):
        fatos.extend(fs)

    ordem = [t for t in temas]
    for t in ordem[:4]:
        if t in TEMAS_LACUNA:
            lacunas.append(t)
            add([_fato_lacuna(t)])
            if t == "clima_futuro":
                add(_fatos_chuva_atual(ponto, hoje, pergunta) + _do_folha(ponto, [("diagnostico", "estação chuvosa e veranicos")], "chuva_epoca"))
            elif t in ("preco", "custo", "venda", "lucro"):
                add(_fatos_renda(ponto, cult)[:2])
            elif t == "produtividade":
                add(_fatos_pam(ponto, cult, "produtividade")[1:2] if cult else [])
                for c in cult[:1]:
                    add(_fatos_ciclo(c)[:1])
            elif t == "semente":
                for c in cult[:1]:
                    add(_fatos_ciclo(c)[:1] + _fatos_faixas(c)[:1])
            elif t == "pragas":
                for c in cult[:1]:
                    add(_fatos_sanidade(c))
            elif t == "adubo":
                add(_fatos_listas_tabela("adubacao_verde")[:1])
                add(_do_folha(ponto, [("solo", "solo estimado")], "solo"))
            elif t == "irrigacao":
                add(_do_folha(ponto, [("eto", "chuva menos ETo")], "agua_balanco"))
        elif t == "chuva_atual":
            add(_fatos_chuva_atual(ponto, hoje, pergunta))
            if not re.search(r"choveu|esse ano|este ano", corrigir_grafia(_norm(pergunta))):
                add(_do_folha(ponto, [("diagnostico", "estação chuvosa e veranicos")], t))
        elif t == "plantar_agora":
            add(_fatos_plantar_agora(ponto, hoje))
        elif t == "veranico":
            add(_do_folha(ponto, [("diagnostico", "estação chuvosa e veranicos")], t) or [_sem_local(t, "o veranico")])
            add(_glossario("veranico")[:1])
        elif t == "chuva_epoca":
            add(_do_folha(ponto, [("diagnostico", "estação chuvosa e veranicos"), ("clima", "chuva média por quinzena")], t) or [_sem_local(t, "a época da chuva")])
        elif t == "solo_nu":
            add(_do_folha(ponto, [("diagnostico", "solo nu")], t) or [_sem_local(t, "a época em que a terra fica descoberta")])
        elif t == "estresse":
            add(_do_folha(ponto, [("diagnostico", "estresse")], t) or [_sem_local(t, "as épocas em que a planta sofre")])
        elif t == "extremos":
            add(_do_folha(ponto, [("extremos", "último ano"), ("extremos", "tendência dos extremos")], t) or [_sem_local(t, "o calor e a chuva forte")])
        elif t == "agua_balanco":
            add(_do_folha(ponto, [("eto", "chuva menos ETo")], t) or [_sem_local(t, "o balanço de água")])
            add(_glossario("evapotranspiração ETo")[:1])
        elif t == "erosao":
            add(_do_folha(ponto, [("risco", "risco de erosão")], t) or [_sem_local(t, "o risco de erosão")])
        elif t in ("previsao", "modelo"):
            if t == "previsao":
                add(_do_folha(ponto, [("previsao", "anomalia prevista"), ("previsao", "faixa de incerteza"), ("previsao", "último composto observado"), ("previsao_limites", "limite da previsão")], t, 2)
                    or [_sem_local(t, "o verde das próximas semanas")])
            else:
                add(_do_folha(ponto or _qualquer_ponto(), [("modelo_skill", "skill por fase"), ("modelo_skill", "persistência e clima"), ("modelo_skill", "locais em que ganha")], t, 2))
        elif t == "limites":
            add(_do_folha(ponto or _qualquer_ponto(), [("limites", "limite dos dados")], t, 2)[:4])
        elif t == "sobre_sulco":
            add([_f(t, "o que o Sulco tem", f"O Sulco tem, para o seu município: chuva e temperatura desde 2001, o verde visto do satélite, o zoneamento do governo, ciclo e clima de {len(_nomes())} culturas, "
                    "solo estimado, o que o município colhe (IBGE) e estudos de rotação e consórcio. Não tem preço, custo nem semente.",
                    "src.llm.conhecimento (inventário das fontes do Sulco)", prio=1,
                    qual="O Sulco tem, para o seu município: chuva e temperatura de vários anos, o verde das plantas visto do satélite, o zoneamento do governo, o ciclo e as faixas de clima das culturas, o solo estimado por mapa, "
                         "o que o município colhe (IBGE) e estudos de rotação e de plantio junto. Não tem preço, custo nem semente.")] + _fatos_sobre_sulco(pergunta, t))
        elif t == "glossario":
            add(_glossario(pergunta))
        elif t == "solo":
            add(_do_folha(ponto, [("solo", "solo estimado")] + ([] if cult else [("risco", "risco de erosão")]), t) or [_sem_local(t, "o solo")])
            for c in cult[:1]:
                add(_fatos_solo_cultura(c, ponto))
            if ponto and re.search(r"fraco|fraca|cansad|pobre|ruim|recuper|melhor|esgotad|sem (forca|vida)", corrigir_grafia(_norm(pergunta))):
                add([_f(t, "nutrientes", "Ainda não temos dado de nutrientes do seu solo (fósforo, potássio): o mapa só estima o tipo de solo, o carbono e a acidez.",
                        "src.app.mvp.solo_estimado (SoilGrids: sem nutrientes)", lacuna=True, prio=2)] + _fatos_listas_tabela("adubacao_verde"))
        elif t == "pam":
            add(_fatos_pam(ponto, cult))
        elif t == "ciclo":
            for c in cult[:2]:
                add(_fatos_ciclo(c))
            if not cult:
                add([_f("ciclo", "ciclo", "Me diga de qual planta você quer saber o ciclo (quantos dias até colher).", "conversa", lacuna=True, prio=1)])
        elif t == "cultura_clima":
            for c in cult[:2]:
                add(_fatos_faixas(c) + _fatos_viabilidade(c, ponto, "cultura_clima")[:1])
            if not cult:
                add([_f("cultura_clima", "cultura", "Me diga de qual planta você quer saber (por exemplo milho ou feijão-caupi).", "conversa", lacuna=True, prio=1)])
        elif t == "viabilidade":
            for c in cult[:2]:
                add(_fatos_viabilidade(c, ponto) + _fatos_zarc(c, ponto)[:1])
            if not cult:
                add([_f("viabilidade", "cultura", "Me diga qual planta você pensa em plantar que eu olho se dá certo no seu local.", "conversa", lacuna=True, prio=1)])
        elif t == "zarc_plantio":
            if not cult and re.search(r"o que (e|eh|significa)|zarc|zoneamento", corrigir_grafia(_norm(pergunta))):
                add([_f(t, "o que é o ZARC", "O ZARC é o zoneamento do Ministério da Agricultura: diz, para cada cultura e município, em que períodos do ano plantar tem menos risco de perder por causa do clima. "
                        "Ele não considera pragas e doenças.", "definição do projeto (src/culturas/zarc.py; docs/27)", prio=1)])
            for c in cult[:2]:
                add(_fatos_zarc(c, ponto) + _fatos_janela(c, ponto))
            if not cult:
                add(_do_folha(ponto, [("diagnostico", "estação chuvosa e veranicos")], t) or [_sem_local(t, "a época de plantio")])
                add([_f("zarc_plantio", "cultura", "Se me disser qual planta, eu mostro o zoneamento do governo para ela.", "conversa", lacuna=True, prio=2)])
        elif t == "por_que_nao":
            for c in cult[:1]:
                add(_fatos_por_que_nao(c, ponto, est))
            if not cult:
                add(_fatos_sobre_sulco("por que sugeriu caminhos", t)[:1] or [_f(t, "cultura", "Me diga qual planta não apareceu que eu olho o motivo.", "conversa", lacuna=True, prio=1)])
        elif t == "consorcio":
            add(_fatos_consorcio(cult))
        elif t == "rotacao_par":
            if len(cult) >= 2:
                add(_fatos_rotacao_par(cult[0], cult[1]))
            elif cult and re.search(r"repet|mesmo lugar|seguid|de novo|outra vez|todo ano", corrigir_grafia(_norm(pergunta))):
                add(_fatos_rotacao_par(cult[0], cult[0]))
            elif cult:
                add(_fatos_depois_de(cult[0], ponto))
            else:
                add(_fatos_sobre_sulco("o que é rotação", t)[:1])
        elif t == "rotacao_conceito":
            add([_f(t, "o que é rotação", "Rotação é plantar uma cultura diferente no mesmo lugar a cada safra, em vez de repetir a mesma. O Sulco compara três caminhos de rotação para o seu local e mostra o que os dados dizem de cada um.",
                    "src.llm.sobre_sulco (como o Sulco funciona) e definição do projeto", prio=1)])
        elif t == "adubacao_verde":
            add(_glossario("adubação verde leguminosa nitrogênio")[:1] + _fatos_listas_tabela("adubacao_verde"))
        elif t == "palhada":
            add(_glossario("palhada cobertura do solo")[:1] + _fatos_listas_tabela("palhada"))
        elif t == "forragem":
            add(_fatos_forragem(ponto))
    # --- ficha completa: busca por similaridade (assuntos que nenhuma regra de tema prevê, e fatos de outros temas que ajudam a mesma resposta)
    melhor = 0.0
    nao_lacuna = [f for f in fatos if not f["lacuna"]]
    if True:        # a ficha completa entra SEMPRE: além dos fatos do tema, a IA recebe os fatos vizinhos (chuva, zoneamento, solo...) para relacionar
        try:
            achados = buscar_ficha(pergunta, ponto, cult)
        except Exception:  # noqa: BLE001
            achados = []
        if achados:
            melhor = achados[0][0]
        have = {f["texto_simples"] for f in fatos}
        novos = [{**f, "prio": min(f["prio"], 2) + (0 if not temas else 1)} for _, f in achados if f["texto_simples"] not in have]
        fatos.extend(novos[: (K_FICHA if not temas else 6)])
        nao_lacuna = [f for f in fatos if not f["lacuna"]]
    # --- acervo (RAG): assuntos de manejo, ou quando nenhuma fonte do Sulco respondeu
    usou_rag = False
    precisa_rag = (not temas) or any(t in TEMAS_RAG for t in temas) or len(nao_lacuna) == 0
    if usar_rag and precisa_rag:
        rag = _fatos_rag(pergunta, buscar_fn)
        if rag:
            usou_rag = True
            fatos.extend(rag)
    precisa_local = (not ponto) and any(f["rotulo"] == "sem município" for f in fatos)
    if precisa_local and len(fatos) > 1:
        fatos = [f for f in fatos if f["rotulo"] != "sem município"] + [f for f in fatos if f["rotulo"] == "sem município"][:1]
    if not any(not f["lacuna"] for f in fatos) and not lacunas and not precisa_local:
        fatos.append(_f("nada", "sem resposta", SEM_RESPOSTA, "roteador: nenhuma fonte do Sulco respondeu", lacuna=True, prio=0))
    # ordem final: o tema que a pergunta citou primeiro, depois a prioridade do fato
    pos = {t: i for i, t in enumerate(temas)}
    fatos.sort(key=lambda f: (0 if f["tema"] in ("franqueza",) else 1, pos.get(f["tema"], 99), f["prio"]))
    if not numeros:                      # o usuário não pediu número: a resposta usa palavras (versão qualitativa de cada fato)
        tinha = any(not f["lacuna"] for f in fatos)
        fatos = sem_numeros(fatos)
        resp = [f for f in fatos if not f["lacuna"] and not f.get("so_comparar")]      # fatos que respondem EM PALAVRAS (os 'so_comparar' só servem à IA)
        if tinha and not resp and not temas:      # nenhum tema e só achados com número da ficha (parecidos por acaso): honesto, 'não achei'
            fatos = [f for f in fatos if f["lacuna"]] + [_f("nada", "sem resposta", SEM_RESPOSTA, "roteador: nenhuma fonte do Sulco respondeu", lacuna=True, prio=0)]
        elif tinha and not resp and not any(f["lacuna"] for f in fatos):
            # só há fatos com número e nenhuma lacuna a dizer: o texto padrão oferece os números (com lacuna, a lacuna já é a resposta: sem frase contraditória)
            fatos.append(_f("nada_numero", "só com número", "Para isso eu tenho os números. Se quiser, é só pedir que eu digo.", "regra: número só se o usuário pedir", prio=1))
    fatos = _cortar(fatos, teto_tokens, max_fatos)
    trechos = []
    for i, f in enumerate(fatos, 1):
        f["id"] = f"F{i}"
        t = f.pop("_trecho", None)
        if t:
            trechos.append({"n": len(trechos) + 1, **t})
    return {"temas": temas, "culturas": cult, "fatos": fatos, "lacunas": lacunas, "precisa_local": precisa_local, "usou_rag": usou_rag, "trechos": trechos,
            "melhor_nota": melhor, "numeros": numeros}


def _qualquer_ponto() -> str | None:
    """As métricas do modelo e os limites valem para todos os locais: usa um ponto qualquer só para ler a folha."""
    try:
        from src.app import mvp as M
        return str(M.carregar_pontos()["ponto_id"].iloc[0])
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------------------------------------ texto padrão (sem LLM)
def texto_padrao_livre(sel: dict, max_palavras: int | None = None) -> str:
    """Resposta SEM IA: a lacuna dita primeiro (quando é o caso), depois 'o que eu tenho' em até 3 frases dos fatos, cada uma com [F#] para conferência
    (`limpar_citacoes` tira os marcadores da tela), e o fecho. Corta frases até caber em `max_palavras`."""
    fatos = sel["fatos"]
    grande = bool(sel.get("grande"))                      # pergunta grande: até 5 frases e ~106 palavras (em vez de 3 e 56)
    max_palavras = max_palavras or (MAX_PALAVRAS_PADRAO_GRANDE if grande else MAX_PALAVRAS_PADRAO)
    lac = [f for f in fatos if f["lacuna"] and f["prio"] == 0 and f["tema"] != "nada"]
    sem_resp = [f for f in fatos if f["tema"] == "nada"]
    resto = [f for f in fatos if f not in lac and f not in sem_resp and not f.get("so_comparar")]     # fato com número sem versão em palavras: só a IA usa
    if sem_resp and not resto:
        return SEM_RESPOSTA
    linhas = [f"{f['texto_simples']} [{f['id']}]" for f in lac[:2]]
    ate = (5 if grande else 3) - min(len(lac), 1)
    corpo = [f"{f['texto_simples']} [{f['id']}]" for f in resto[:ate + (1 if not lac else 0)]]
    if lac and corpo:
        linhas.append("O que eu tenho para isso:")
    linhas += corpo
    while len(linhas) > 1 and contar_palavras(limpar_citacoes("\n".join(linhas + [FECHO]))) > max_palavras:
        linhas.pop()
    if linhas and linhas[-1] == "O que eu tenho para isso:":
        linhas.pop()
    return "\n".join(linhas + [FECHO])
