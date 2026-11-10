"""
dicionarios.py
--------------
Mapeamentos de código -> rótulo extraídos do arquivo Dicionario_de_dados.xlsx.
Usados para decodificar os campos categóricos do Novo CAGED em descrições legíveis.

Fonte: Dicionario_de_dados.xlsx (abas seção, graudeinstrução, tipomovimentação, etc.)
"""

# Seção CNAE 2.0 (setor econômico). As seções B, C, D e E compõem a INDÚSTRIA.
SECAO = {
    "A": "Agricultura, Pecuária, Produção Florestal, Pesca e Aquicultura",
    "B": "Indústrias Extrativas",
    "C": "Indústrias de Transformação",
    "D": "Eletricidade e Gás",
    "E": "Água, Esgoto, Gestão de Resíduos e Descontaminação",
    "F": "Construção",
    "G": "Comércio, Reparação de Veículos",
    "H": "Transporte, Armazenagem e Correio",
    "I": "Alojamento e Alimentação",
    "J": "Informação e Comunicação",
    "K": "Atividades Financeiras e de Seguros",
    "L": "Atividades Imobiliárias",
    "M": "Atividades Profissionais, Científicas e Técnicas",
    "N": "Atividades Administrativas e Serviços Complementares",
    "O": "Administração Pública, Defesa e Seguridade Social",
    "P": "Educação",
    "Q": "Saúde Humana e Serviços Sociais",
    "R": "Artes, Cultura, Esporte e Recreação",
    "S": "Outras Atividades de Serviços",
    "T": "Serviços Domésticos",
    "U": "Organismos Internacionais",
    "Z": "Não identificado",
}

# Seções consideradas "indústria" para o foco do desafio.
SECOES_INDUSTRIAIS = ["B", "C", "D", "E"]

GRAU_INSTRUCAO = {
    "1": "Analfabeto",
    "2": "Até 5ª Incompleto",
    "3": "5ª Completo Fundamental",
    "4": "6ª a 9ª Fundamental",
    "5": "Fundamental Completo",
    "6": "Médio Incompleto",
    "7": "Médio Completo",
    "8": "Superior Incompleto",
    "9": "Superior Completo",
    "10": "Mestrado",
    "11": "Doutorado",
    "80": "Pós-Graduação completa",
    "99": "Não Identificado",
}

# Ordem crescente de escolaridade, para análises ordinais (ranking).
GRAU_INSTRUCAO_ORDEM = {
    "1": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5, "7": 6,
    "8": 7, "9": 8, "80": 9, "10": 10, "11": 11, "99": None,
}

TIPO_MOVIMENTACAO = {
    "10": "Admissão por primeiro emprego",
    "20": "Admissão por reemprego",
    "25": "Admissão por contrato prazo determinado",
    "31": "Desligamento demissão sem justa causa",
    "32": "Desligamento demissão com justa causa",
    "33": "Culpa Recíproca",
    "35": "Admissão por reintegração",
    "40": "Desligamento a pedido",
    "43": "Término contrato prazo determinado",
    "45": "Desligamento por término de contrato",
    "50": "Desligamento por aposentadoria",
    "60": "Desligamento por morte",
    "70": "Admissão por transferência",
    "80": "Desligamento por transferência",
    "90": "Desligamento por acordo",
    "97": "Admissão de tipo ignorado",
    "98": "Desligamento de tipo ignorado",
    "99": "Não Identificado",
}

SEXO = {"1": "Homem", "3": "Mulher", "9": "Não Identificado"}

RACA_COR = {
    "1": "Branca", "2": "Preta", "3": "Parda", "4": "Amarela",
    "5": "Indígena", "6": "Não informada", "9": "Não Identificado",
}

CATEGORIA = {
    "101": "Empregado CLT (geral)",
    "102": "Trabalhador rural pequeno prazo",
    "103": "Aprendiz",
    "104": "Doméstico",
    "105": "Contrato a termo Lei 9.601/98",
    "106": "Trabalhador temporário Lei 6.019/74",
    "107": "Verde e Amarelo (sem antecipação FGTS)",
    "108": "Verde e Amarelo (com antecipação FGTS)",
    "111": "Contrato intermitente",
    "999": "Não Identificado",
}

TAM_ESTAB = {
    "1": "Zero", "2": "1 a 4", "3": "5 a 9", "4": "10 a 19",
    "5": "20 a 49", "6": "50 a 99", "7": "100 a 249", "8": "250 a 499",
    "9": "500 a 999", "10": "1000 ou mais",
    "90": "Não Informado", "97": "Não se Aplica", "98": "Inválido", "99": "Ignorado",
}
