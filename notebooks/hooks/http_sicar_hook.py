from requests.adapters import HTTPAdapter


class SiCARHTTPAdapter(HTTPAdapter):
    """Adapter HTTPS com configuração TLS específica do GeoServer CAR.

    Força TLSv1.2 e o cipher AES256-GCM-SHA384, além de desabilitar a
    verificação de hostname/certificado exigida por esse endpoint.
    """

    def init_poolmanager(self, *args, **kwargs):
        """Inicializa o pool de conexões com o contexto SSL customizado.

        Args:
            *args: Argumentos posicionais repassados ao pool manager.
            **kwargs: Argumentos nomeados repassados ao pool manager. O
                contexto SSL customizado é injetado em ``ssl_context``.

        Returns:
            Pool manager SSL configurado pelo ``HTTPAdapter`` base.
        """
        import ssl
        from urllib3.util.ssl_ import create_urllib3_context

        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers("AES256-GCM-SHA384")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class HttpSicarHook:
    """Cliente WFS para consulta de imóveis rurais do SiCAR.

    Expõe métodos para buscar features do GeoServer CAR, converter a
    geometria para WKT e, opcionalmente, paginar até o fim da UF.
    """

    def __init__(self):
        """Inicializa a sessão HTTP com o adapter SiCAR."""
        import requests

        self.url = "https://geoserver.car.gov.br/geoserver/sicar/ows"

        self.session = requests.Session()
        self.session.mount("https://", SiCARHTTPAdapter())

        super().__init__()

    def _fetch_page(
        self,
        uf: str,
        page_size: int,
        start_index: int,
        projection: str,
    ) -> dict:
        """Solicita uma página de features ao serviço WFS do SiCAR.

        Args:
            uf: Sigla da unidade federativa já normalizada (minúscula).
            page_size: Quantidade máxima de features retornadas (``count``).
            start_index: Índice inicial da página (``startIndex`` do WFS).
            projection: Sistema de referência espacial (``srsName``), por
                exemplo ``EPSG:4326``.

        Returns:
            FeatureCollection em formato GeoJSON (dicionário) retornada
            pelo GeoServer.
        """
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": f"sicar:sicar_imoveis_{uf}",
            "outputFormat": "application/json",
            "srsName": projection,
            "count": page_size,
            "startIndex": start_index,
        }
        response = self.session.get(self.url, params=params, verify=False, timeout=120)
        return response.json()

    def _features_to_records(
        self,
        payload: dict,
        uf: str,
        page_size: int,
        start_index: int,
        is_pagination: bool,
    ) -> list[dict]:
        """Converte features GeoJSON em registros com geometria WKT.

        Cada registro inclui os atributos da feature, a geometria em WKT
        e colunas de checagem da página (totais, página atual, faltantes).

        Args:
            payload: FeatureCollection retornada por ``_fetch_page``.
            uf: Sigla da unidade federativa associada à consulta.
            page_size: Tamanho da página usado para calcular ``page``.
            start_index: Índice inicial da página convertida.
            is_pagination: Indica se a consulta está em modo paginação.

        Returns:
            Lista de dicionários pronta para uso em ``pandas.DataFrame``,
            com colunas de metadados ``total_features``, ``number_matched``,
            ``number_returned``, ``start_index``, ``page``, ``remaining``,
            ``uf`` e ``is_pagination``.
        """
        from shapely.geometry import shape
        from shapely.wkt import dumps

        features = payload.get("features") or []
        number_matched = payload.get("numberMatched")
        total_features = payload.get("totalFeatures", number_matched)
        number_returned = payload.get("numberReturned", len(features))

        if total_features is None:
            remaining = None
        else:
            remaining = max(0, int(total_features) - start_index - int(number_returned))

        records: list[dict] = []
        for feature in features:
            record = dict(feature.get("properties") or {})
            geometry = feature.get("geometry")
            record["geometry"] = dumps(shape(geometry)) if geometry else None
            record["total_features"] = total_features
            record["number_matched"] = number_matched
            record["number_returned"] = number_returned
            record["start_index"] = start_index
            record["page"] = start_index // page_size if page_size else 0
            record["remaining"] = remaining
            record["uf"] = uf
            record["is_pagination"] = is_pagination
            records.append(record)

        return records

    def get_sicar_data(
        self,
        uf: str,
        page_size: int = 1_000,
        initial_page: int = 0,
        projection: str = "EPSG:4326",
        is_pagination: bool = False,
    ) -> list[dict]:
        """Busca imóveis do SiCAR para uma UF.

        Quando ``is_pagination`` é ``False``, retorna apenas a página
        solicitada. Quando ``True``, pagina até esgotar os registros
        disponíveis da UF.

        Args:
            uf: Sigla da unidade federativa (ex.: ``"SC"``).
            page_size: Quantidade de features por página.
            initial_page: Índice inicial (``startIndex``) da primeira
                requisição.
            projection: Sistema de referência espacial desejado
                (``srsName``), padrão ``EPSG:4326``.
            is_pagination: Se ``True``, continua buscando páginas até o
                fim da UF; se ``False``, busca somente uma página.

        Returns:
            Lista de registros com atributos do imóvel, geometria em WKT
            e colunas de metadados da API para uso direto em DataFrame.
        """
        uf_normalized = uf.strip().lower()
        start_index = initial_page
        records: list[dict] = []

        while True:
            payload = self._fetch_page(
                uf=uf_normalized,
                page_size=page_size,
                start_index=start_index,
                projection=projection,
            )
            page_records = self._features_to_records(
                payload=payload,
                uf=uf_normalized,
                page_size=page_size,
                start_index=start_index,
                is_pagination=is_pagination,
            )
            records.extend(page_records)

            if not is_pagination:
                break

            features = payload.get("features") or []
            fetched = len(features)
            number_matched = payload.get("numberMatched")
            total = payload.get("totalFeatures", number_matched)
            start_index += fetched

            if (
                fetched == 0
                or (total is not None and start_index >= int(total))
                or fetched < page_size
            ):
                break

        return records
