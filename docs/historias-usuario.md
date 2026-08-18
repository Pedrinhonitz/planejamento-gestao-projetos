# Histórias de usuário

Produto: **Sistema de Apoio à Priorização da Fiscalização Ambiental de Imóveis Rurais**.

## Contexto

O monitoramento por sensoriamento remoto (MapBiomas Alertas, DETER, PRODES) e o Cadastro Ambiental Rural (CAR/SiCAR) geram um volume de ocorrências maior do que as equipes de fiscalização conseguem atender. Identificar um alerta de desmatamento **não** diz qual ocorrência é mais urgente ou de maior impacto ambiental. A Portaria IBAMA nº 217/2023 exige análise de risco e definição de prioridades no planejamento da fiscalização. Este produto integra dados públicos do CAR e do MapBiomas, aplica um modelo de Machine Learning e apresenta, em uma aplicação Streamlit, uma lista ranqueada, explicável e auditável vinculando alerta, imóvel e responsável para que o deslocamento de campo gere mais autuações por equipe, sem exigir analista GIS.

## Personas

| Persona | Papel |
| --- | --- |
| Fiscal ambiental estadual/municipal | Planeja e executa fiscalização em órgãos como IMA-SC e secretarias municipais. |
| Policial Militar Ambiental | Atua em campo com deslocamento limitado e precisa escolher alvos de maior impacto. |
| Membro do Ministério Público | Acompanha evidências e priorização para medidas legais. |
| Analista IBAMA / ICMBio | Planeja ações federais com análise de risco (Portaria 217/2023). |
| Gestor de equipe de fiscalização | Distribui rotas e mede produtividade (autuações por equipe deslocada). |
| Consultor / certificadora | Verifica conformidade ambiental de imóveis para clientes. |
| Analista de compliance (banco/trading) | Avalia risco socioambiental de cadeias e financiamentos. |
| Pesquisador / ONG | Consulta dados públicos para pesquisa e advocacy, sem poder de autuação. |

## Épico 1 — Priorização de alertas

### US-01 — Lista de alertas ordenada por prioridade

**Como** fiscal ambiental estadual/municipal, **quero** ver os alertas de desmatamento ordenados por urgência e impacto ambiental, **para** concentrar a fiscalização nas ocorrências que mais importam.

**Critérios de aceite**

- Dado que existem alertas carregados na base, quando abro a aplicação, então a lista principal está ordenada por pontuação de prioridade (maior primeiro).
- Dado um alerta na lista, quando o visualizo, então vejo pontuação de prioridade, município e data do alerta.
- Dado dois alertas com pontuações distintas, quando comparo a ordem, então o de maior prioridade aparece acima.

### US-02 — Filtro por município e região

**Como** gestor de equipe de fiscalização, **quero** filtrar alertas por município e região, **para** montar o roteiro da equipe na área de atuação.

**Critérios de aceite**

- Dado a lista ranqueada, quando seleciono um município, então só aparecem alertas daquele município, ainda ordenados por prioridade.
- Dado um filtro de região (ex.: estado ou recorte territorial), quando o aplico, então a lista e o mapa refletem apenas esse recorte.
- Dado filtros ativos, quando os removo, então a lista volta ao conjunto completo.

### US-03 — Mais autuações por equipe em campo

**Como** gestor de equipe de fiscalização, **quero** trabalhar a partir dos alertas de maior prioridade já vinculados ao imóvel, **para** aumentar o número de autuações por deslocamento de equipe.

**Critérios de aceite**

- Dado a lista priorizada, quando seleciono os N primeiros alertas de um município, então obtenho imóvel, responsável e localização para montar a saída de campo.
- Dado um alerta priorizado, quando o abro, então não preciso cruzar manualmente MapBiomas e CAR para saber onde ir e a quem se dirige a ação.

## Épico 2 — Vínculo cadastral (alerta, imóvel e responsável)

### US-04 — Cruzar alerta MapBiomas com o imóvel no CAR

**Como** fiscal ambiental, **quero** que cada alerta seja associado automaticamente ao imóvel rural do SiCAR, **para** não interpolar camadas GIS à mão.

**Critérios de aceite**

- Dado um alerta com geometria, quando o sistema processa a integração CAR–MapBiomas, então o alerta fica ligado a um (ou mais) imóveis cuja área intersecta a ocorrência.
- Dado um alerta vinculado, quando o abro, então vejo identificador do CAR e dados cadastrais básicos do imóvel.
- Dado um alerta sem interseção cadastral, quando o visualizo, então o sistema indica que não houve vínculo automático.

### US-05 — Identificar o responsável pelo imóvel

**Como** Policial Militar Ambiental, **quero** ver o responsável pelo imóvel ligado ao alerta, **para** direcionar a abordagem em campo e o auto de infração.

**Critérios de aceite**

- Dado um alerta vinculado a um imóvel CAR, quando consulto o detalhe, então vejo o nome (ou razão social) do responsável registrado no SiCAR.
- Dado imóvel com mais de um responsável, quando abro o detalhe, então todos são listados.
- Dado dados cadastrais incompletos, quando o vínculo existe só parcialmente, então o sistema deixa explícito o que falta.

## Épico 3 — Explicabilidade e auditoria

### US-06 — Entender por que o alerta foi priorizado

**Como** analista do IBAMA / ICMBio, **quero** ver os fatores que pesaram no ranking (modelo e camadas auxiliares), **para** justificar a escolha da ocorrência.

**Critérios de aceite**

- Dado um alerta ranqueado, quando abro a explicação, então vejo os principais fatores (ex.: sobreposição com UC, TI, embargo, histórico, área desmatada).
- Dado a explicação, quando a leio, então consigo relatar o motivo da prioridade sem abrir o código do modelo.
- Dado dois alertas, quando comparo as explicações, então as diferenças de fatores são compreensíveis.

### US-07 — Priorização auditável e alinhada à Portaria 217/2023

**Como** membro do Ministério Público, **quero** uma trilha auditável da priorização, **para** conferir que o planejamento segue análise de risco prevista na Portaria IBAMA nº 217/2023.

**Critérios de aceite**

- Dado um ranking gerado, quando solicito a trilha, então constam data/hora, versão do modelo, fontes de dados e critérios utilizados.
- Dado uma ocorrência já priorizada, quando a reconsulto depois, então o histórico daquela pontuação permanece recuperável.
- Dado o uso da ferramenta no planejamento, quando registro a ação, então a priorização fica documentada de forma reproduzível.

## Épico 4 — Uso sem analista GIS

### US-08 — Consultar lista e mapa no Streamlit

**Como** fiscal ambiental, **quero** consultar alertas em uma aplicação web (Streamlit) com lista e mapa, **para** usar o sistema sem analista de SIG.

**Critérios de aceite**

- Dado acesso à aplicação, quando abro o endereço no navegador, então vejo lista ranqueada e mapa dos alertas filtrados.
- Dado um alerta na lista, quando o seleciono, então o mapa destaca a geometria correspondente.
- Dado um usuário sem software GIS instalado, quando navega na aplicação, então consegue filtrar, ordenar e abrir o detalhe do alerta.

## Épico 5 — Ciclo de feedback e retreino

### US-09 — Registrar resultado da fiscalização

**Como** Policial Militar Ambiental, **quero** registrar o resultado da ida a campo (autuação, embargo, sem infração, imóvel não localizado), **para** que o modelo seja retreinado com o que de fato ocorreu.

**Critérios de aceite**

- Dado um alerta priorizado, quando registro o resultado da fiscalização, então o status fica associado àquele alerta.
- Dado resultados acumulados, quando a equipe de manutenção atualiza o modelo, então esses registros entram no conjunto de treino.
- Dado um alerta já fiscalizado, quando outro usuário o vê, então o status de campo aparece na listagem.

## Épico 6 — Dados públicos e camadas auxiliares

### US-10 — Usar apenas dados públicos e gratuitos

**Como** gestor de órgão ambiental, **quero** que a priorização use só fontes públicas (MapBiomas, SiCAR, INPE e camadas oficiais), **para** operar sem custo de dado comercial e com transparência.

**Critérios de aceite**

- Dado o pipeline de dados, quando consulto as fontes, então constam apenas bases públicas (MapBiomas Alertas, SiCAR, DETER/PRODES quando aplicável, UC, TI, embargos).
- Dado um alerta na interface, quando abro a origem, então vejo a referência da base pública utilizada.
- Dado a proposta de valor do canvas, quando um novo usuário acessa o núcleo da ferramenta, então não há cobrança por alerta adicional (custo marginal zero por usuário).

### US-11 — Considerar UC, TI e áreas embargadas

**Como** fiscal ambiental, **quero** que sobreposição com Unidade de Conservação, Terra Indígena e área embargada aumente a prioridade, **para** tratar primeiro as ocorrências de maior gravidade legal e socioambiental.

**Critérios de aceite**

- Dado um alerta sobreposto a UC, TI ou embargo, quando o modelo pontua, então esses fatores entram na prioridade e na explicação.
- Dado um alerta fora dessas camadas, quando o comparo com um alerta sobreposto, então o sobreposto não fica sistematicamente abaixo só por área ou data.
- Dado a ficha do alerta, quando a abro, então vejo claramente se há interseção com UC, TI e/ou embargo.

## Épico 7 — Atores privados, academia e sociedade

### US-12 — Consulta para compliance sem poder de autuação

**Como** analista de compliance de banco ou trading, **quero** consultar a prioridade e o vínculo alerta–imóvel, **para** avaliar risco socioambiental de um imóvel ou cadeia, sem emitir auto de infração.

**Critérios de aceite**

- Dado acesso de consulta, quando busco um imóvel ou recorte, então vejo alertas, prioridade e responsável cadastral.
- Dado o perfil de compliance, quando uso a aplicação, então não há fluxo de lavratura de auto — apenas consulta e exportação da evidência.
- Dado a mesma busca, quando sou consultor ou certificadora, então obtenho o mesmo recorte informativo para due diligence.

### US-13 — Pesquisa e transparência com repositório aberto

**Como** pesquisador ou integrante de ONG socioambiental, **quero** acessar a ferramenta e o repositório aberto, **para** reproduzir análises e comunicar o método de priorização.

**Critérios de aceite**

- Dado o repositório no GitHub, quando o clono, então a documentação descreve dados, modelo e aplicação Streamlit.
- Dado a aplicação, quando consulto alertas em um recorte, então os resultados são derivados das mesmas fontes públicas usadas pelos órgãos.
- Dado o uso acadêmico, quando cito o método, então a explicação do ranking e as fontes estão documentadas.
