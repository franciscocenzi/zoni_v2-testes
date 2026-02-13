"""Análise de inclinação para raster de valores contínuos (graus)."""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from qgis.core import (
    QgsRasterLayer,
    QgsGeometry,
    QgsRectangle,
    QgsRasterBlock,
    QgsPointXY,
    QgsCoordinateTransform,
    QgsProject,
    QgsRaster,
    QgsRasterDataProvider
)


@dataclass
class ResultadoInclinacao:
    """
    Resultado da análise de inclinação do terreno.
    """
    faixas: List[Dict[str, Any]]  # Lista de dicionários com faixas de inclinação
    area_total_m2: float  # Área total analisada
    area_app_inclinacao_m2: float  # Área com APP por inclinação
    percentual_app_inclinacao: float  # Percentual de APP por inclinação
    mensagens: List[str]  # Mensagens informativas
    tem_app_por_inclinacao: bool  # Se há APP por inclinação
    estatisticas: Optional[Dict[str, Any]] = None  # Estatísticas adicionais


def classificar_inclinacao(valor_graus: float) -> Tuple[int, str, bool]:
    """
    Classifica um valor de inclinação em graus nas categorias pré-definidas.
    
    Args:
        valor_graus: Valor da inclinação em graus
    
    Returns:
        Tupla (categoria_id, rótulo, é_app)
    """
    if valor_graus <= 3.0:
        return (1, "≤ 3°", False)
    elif valor_graus <= 8.0:
        return (2, "3° - 8°", False)
    elif valor_graus <= 15.0:
        return (3, "8° - 15°", False)
    elif valor_graus <= 30.0:
        return (4, "15° - 30°", False)
    elif valor_graus <= 45.0:
        return (5, "30° - 45°", False)
    else:  # > 45°
        return (6, "> 45° (APP)", True)


def obter_categorias_completas() -> Dict[int, Dict[str, Any]]:
    """
    Retorna as categorias completas com todas as informações.
    """
    return {
        1: {"id": 1, "label": "≤ 3°", "cor": "#1a9641", "app": False, "min": 0.0, "max": 3.0},
        2: {"id": 2, "label": "3° - 8°", "cor": "#fbfdbc", "app": False, "min": 3.0, "max": 8.0},
        3: {"id": 3, "label": "8° - 15°", "cor": "#fee4a1", "app": False, "min": 8.0, "max": 15.0},
        4: {"id": 4, "label": "15° - 30°", "cor": "#fec981", "app": False, "min": 15.0, "max": 30.0},
        5: {"id": 5, "label": "30° - 45°", "cor": "#fdae61", "app": False, "min": 30.0, "max": 45.0},
        6: {"id": 6, "label": "> 45° (APP)", "cor": "#d7191c", "app": True, "min": 45.0, "max": 90.0},
    }


def analisar_inclinacao_terreno(lote_geom: QgsGeometry, camada_inclinacao: QgsRasterLayer, 
                               area_lote_m2: Optional[float] = None) -> ResultadoInclinacao:
    """
    Analisa raster de valores contínuos de inclinação (graus).
    
    Args:
        lote_geom: QgsGeometry do lote (deve estar no mesmo CRS do raster)
        camada_inclinacao: QgsRasterLayer com valores de inclinação em graus (0-73.53)
        area_lote_m2: Área do lote em m² (opcional, para validação)
    
    Returns:
        ResultadoInclinacao com os resultados da análise
    """
    try:
        print(f"=== ANÁLISE DE INCLINAÇÃO INICIADA ===")
        print(f"Camada raster: {camada_inclinacao.name()}")
        
        # 1. VERIFICAÇÕES INICIAIS
        if not camada_inclinacao.isValid():
            return _resultado_erro_objeto("Camada de inclinação inválida")
        
        if lote_geom.isEmpty():
            return _resultado_erro_objeto("Geometria do lote vazia")
        
        # 2. OBTER INFORMAÇÕES DO RASTER
        provider = camada_inclinacao.dataProvider()
        x_res = camada_inclinacao.rasterUnitsPerPixelX()
        y_res = camada_inclinacao.rasterUnitsPerPixelY()
        area_pixel_m2 = abs(x_res * y_res)
        
        print(f"Resolução do raster: {x_res:.2f} x {y_res:.2f} m/pixel")
        print(f"Área por pixel: {area_pixel_m2:.2f} m²")
        
        # 3. OBTER EXTENSÃO E INTERSEÇÃO
        extent_raster = camada_inclinacao.extent()
        extent_lote = lote_geom.boundingBox()
        extent = extent_raster.intersect(extent_lote)
        
        if extent.isEmpty():
            return _resultado_erro_objeto("Raster não cobre a área do lote")
        
        print(f"Extensão de interseção: {extent.toString()}")
        
        # 4. CALCULAR TAMANHO DO BLOCO EM PIXELS
        cols = max(1, int(extent.width() / x_res) + 1)
        rows = max(1, int(extent.height() / y_res) + 1)
        
        print(f"Tamanho do bloco: {cols} x {rows} pixels")
        
        # 5. LER BLOCO DE PIXELS
        block = provider.block(1, extent, cols, rows)
        
        if block is None or block.data() is None:
            return _resultado_erro_objeto("Não foi possível ler dados do raster")
        
        # 6. OBTER VALOR DE NoData
        nodata = None
        if provider.sourceHasNoDataValue(1):
            nodata = provider.sourceNoDataValue(1)
            print(f"Valor NoData detectado: {nodata}")
        
        # 7. CONTAR PIXELS POR CATEGORIA
        categorias = obter_categorias_completas()
        contadores = {cat_id: 0 for cat_id in categorias.keys()}
        pixels_totais = 0
        pixels_validos = 0
        
        for row in range(rows):
            for col in range(cols):
                # Coordenada do centro do pixel
                x = extent.xMinimum() + col * x_res + x_res/2
                y = extent.yMaximum() - row * y_res - y_res/2
                
                # Verificar se pixel está dentro do polígono
                ponto = QgsPointXY(x, y)
                ponto_geom = QgsGeometry.fromPointXY(ponto)
                
                if lote_geom.contains(ponto_geom):
                    pixels_totais += 1
                    valor = block.value(row, col)
                    
                    # Ignorar NoData
                    if nodata is not None and abs(float(valor) - float(nodata)) < 0.0001:
                        continue
                    
                    # Converter para float
                    try:
                        valor_graus = float(valor)
                        
                        # Classificar
                        if 0.0 <= valor_graus <= 90.0:  # Faixa válida
                            cat_id, label, is_app = classificar_inclinacao(valor_graus)
                            contadores[cat_id] += 1
                            pixels_validos += 1
                    except (ValueError, TypeError):
                        continue
        
        print(f"Pixels totais no lote: {pixels_totais}")
        print(f"Pixels válidos (classificados): {pixels_validos}")
        
        if pixels_validos == 0:
            return _resultado_erro_objeto("Nenhum pixel válido dentro do lote")
        
        # 8. CALCULAR RESULTADOS POR CATEGORIA
        resultados = []
        area_total_m2 = pixels_validos * area_pixel_m2
        area_app_m2 = 0
        
        for cat_id, info in categorias.items():
            count = contadores[cat_id]
            if count > 0:
                area_m2 = count * area_pixel_m2
                percentual = (count / pixels_validos * 100) if pixels_validos > 0 else 0
                
                if info["app"]:
                    area_app_m2 += area_m2
                
                resultados.append({
                    "faixa": info["label"],
                    "area_m2": round(area_m2, 2),
                    "percentual": round(percentual, 2),
                    "cor": info["cor"],
                    "app": info["app"],
                    "min_graus": info["min"],
                    "max_graus": info["max"],
                    "count": count
                })
        
        # Ordenar por faixa (do menor para maior)
        ordem_faixas = ["≤ 3°", "3° - 8°", "8° - 15°", "15° - 30°", "30° - 45°", "> 45° (APP)"]
        resultados.sort(key=lambda x: ordem_faixas.index(x["faixa"]))
        
        # 9. VALIDAR COM ÁREA DO LOTE
        mensagens = []
        if area_lote_m2 is not None and area_lote_m2 > 0:
            diferenca_percentual = abs((area_total_m2 - area_lote_m2) / area_lote_m2 * 100)
            
            if diferenca_percentual > 20:
                mensagens.append(
                    f"Atenção: Diferença de {diferenca_percentual:.1f}% entre área analisada "
                    f"({area_total_m2:.2f} m²) e área do lote ({area_lote_m2:.2f} m²)"
                )
            else:
                mensagens.append(f"Área analisada: {area_total_m2:.2f} m² (coerente)")
        else:
            mensagens.append(f"Área analisada: {area_total_m2:.2f} m²")
        
        # 10. CALCULAR APP POR INCLINAÇÃO
        percentual_app = (area_app_m2 / area_total_m2 * 100) if area_total_m2 > 0 else 0
        
        mensagens.extend([
            f"Raster analisado: {camada_inclinacao.name()}",
            f"Resolução: {x_res:.2f} x {y_res:.2f} m/pixel",
            f"Pixels válidos analisados: {pixels_validos}"
        ])
        
        if area_app_m2 > 0:
            mensagens.append(f"APP por inclinação (>45°): {area_app_m2:.2f} m² ({percentual_app:.1f}%)")
        
        # 11. ESTATÍSTICAS
        estatisticas = {
            "pixels_totais": pixels_totais,
            "pixels_validos": pixels_validos,
            "resolucao_x": x_res,
            "resolucao_y": y_res,
            "area_pixel_m2": area_pixel_m2,
            "percentual_cobertura": (pixels_validos / pixels_totais * 100) if pixels_totais > 0 else 0,
            "valores_nodata": nodata,
            "crs": camada_inclinacao.crs().authid() if camada_inclinacao.crs() else "N/A"
        }
        
        print(f"=== ANÁLISE DE INCLINAÇÃO CONCLUÍDA ===")
        print(f"Área total analisada: {area_total_m2:.2f} m²")
        print(f"APP por inclinação: {area_app_m2:.2f} m² ({percentual_app:.2f}%)")
        
        # 12. DEBUG: Mostrar contagem por categoria
        print("Contagem por categoria:")
        for resultado in resultados:
            print(f"  {resultado['faixa']}: {resultado['count']} pixels = {resultado['area_m2']:.2f} m²")
        
        return ResultadoInclinacao(
            faixas=resultados,
            area_total_m2=round(area_total_m2, 2),
            area_app_inclinacao_m2=round(area_app_m2, 2),
            percentual_app_inclinacao=round(percentual_app, 2),
            mensagens=mensagens,
            tem_app_por_inclinacao=area_app_m2 > 0,
            estatisticas=estatisticas
        )
        
    except Exception as e:
        import traceback
        print(f"ERRO NA ANÁLISE DE INCLINAÇÃO: {str(e)}")
        print(traceback.format_exc())
        return _resultado_erro_objeto(f"Erro técnico na análise: {str(e)}")


def _resultado_erro_objeto(mensagem: str) -> ResultadoInclinacao:
    """Retorna objeto ResultadoInclinacao para erro."""
    return ResultadoInclinacao(
        faixas=[],
        area_total_m2=0,
        area_app_inclinacao_m2=0,
        percentual_app_inclinacao=0,
        mensagens=[mensagem],
        tem_app_por_inclinacao=False,
        estatisticas={}
    )


# Função auxiliar para verificar valores do raster
def analisar_estatisticas_raster(camada_inclinacao: QgsRasterLayer, amostras: int = 1000) -> Dict[str, Any]:
    """
    Analisa estatísticas básicas do raster para debug.
    """
    try:
        print(f"=== ANÁLISE ESTATÍSTICAS DO RASTER ===")
        print(f"Camada: {camada_inclinacao.name()}")
        
        provider = camada_inclinacao.dataProvider()
        extent = camada_inclinacao.extent()
        
        valores = []
        import random
        
        for _ in range(amostras):
            x = random.uniform(extent.xMinimum(), extent.xMaximum())
            y = random.uniform(extent.yMinimum(), extent.yMaximum())
            
            ident = provider.identify(QgsPointXY(x, y), QgsRaster.IdentifyFormatValue)
            if ident.isValid():
                resultado = ident.results()
                if resultado:
                    valor = list(resultado.values())[0]
                    try:
                        valores.append(float(valor))
                    except:
                        continue
        
        if valores:
            print(f"  Mínimo: {min(valores):.2f}°")
            print(f"  Máximo: {max(valores):.2f}°")
            print(f"  Média: {np.mean(valores):.2f}°")
            print(f"  Amostras: {len(valores)}")
            
            # Histograma básico
            bins = [0, 3, 8, 15, 30, 45, 90]
            histograma, _ = np.histogram(valores, bins=bins)
            
            print("  Distribuição nas faixas:")
            for i in range(len(histograma)):
                percentual = (histograma[i] / len(valores) * 100) if len(valores) > 0 else 0
                print(f"    {bins[i]:.0f}-{bins[i+1]:.0f}°: {histograma[i]} pixels ({percentual:.1f}%)")
        
        return {"valores": valores}
        
    except Exception as e:
        print(f"Erro na análise estatística: {e}")
        return {}


# Função de compatibilidade
def analisar_inclinacao_raster_classificado(geom_lote, camada_raster):
    """
    Função original mantida para compatibilidade.
    """
    return analisar_inclinacao_terreno(geom_lote, camada_raster)