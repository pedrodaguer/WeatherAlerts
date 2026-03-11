import urllib.parse

import requests


def get_cities_by_day(day_of_week):
    """
    Return cities to receive alerts based on weekday.

    Args:
        day_of_week: 0=Monday through 6=Sunday.

    Returns:
        List of city keys for sending alerts.
    """
    if 0 <= day_of_week <= 3:
        return ["blumenau"]
    elif day_of_week == 4:
        return ["blumenau", "itajai"]
    elif day_of_week in (5, 6):
        return ["itajai"]
    return []


def send_weather_alert(phone_number, api_key, weather_info_list):
    """Send weather alert via CallMeBot WhatsApp API."""
    message = format_weather_message(weather_info_list)
    encoded_message = urllib.parse.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone_number}&text={encoded_message}&apikey={api_key}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        print("✓ Alerta meteorológico enviado com sucesso!")
        return response
    except requests.exceptions.RequestException as e:
        print(f"✗ Erro ao enviar alerta: {e}")
        raise


def get_clothing_suggestion(apparent_min, apparent_max):
    """Return clothing guidance for a person who feels cold easily."""
    try:
        apparent_min = float(apparent_min)
        apparent_max = float(apparent_max)
    except (TypeError, ValueError):
        return "Roupa sugerida: Nao foi possivel estimar hoje"

    if apparent_min <= 10:
        base = "casaco pesado + blusa de manga longa + calca"
    elif apparent_min <= 14:
        base = "casaco medio + blusa"
    elif apparent_min <= 18:
        base = "casaco leve ou moletom fino"
    elif apparent_min <= 22:
        base = "camiseta com sobreposicao leve"
    else:
        base = "roupas leves"

    if apparent_max - apparent_min >= 8 and apparent_max >= 24:
        return f"Roupa sugerida: {base}; use camadas para tirar ao longo do dia"

    return f"Roupa sugerida: {base}"


def format_weather_message(weather_info_list):
    """Format weather data into a readable message string."""
    def safe_round(value, decimals=1):
        try:
            return round(float(value), decimals)
        except (TypeError, ValueError):
            return "N/A"

    message = "*BOM DIA!*\n\n"

    for idx, weather_info in enumerate(weather_info_list):
        if idx > 0:
            message += "\n─────────────\n\n"

        if "city" in weather_info:
            city_name = weather_info["city"].upper()
            message += f"*{city_name}*\n"

        if "daily" in weather_info:
            daily = weather_info["daily"]
            temp_max = safe_round(daily.get("temp_max", "N/A"))
            temp_min = safe_round(daily.get("temp_min", "N/A"))
            apparent_max = safe_round(daily.get("apparent_temp_max", "N/A"))
            apparent_min = safe_round(daily.get("apparent_temp_min", "N/A"))
            precipitation = safe_round(daily.get("precipitation", "N/A"))
            clothing_suggestion = get_clothing_suggestion(
                daily.get("apparent_temp_min", "N/A"),
                daily.get("apparent_temp_max", "N/A"),
            )

            message += f"Temperatura: {temp_max}°C | {temp_min}°C\n"
            message += f"Sensacao Termica: {apparent_max}°C | {apparent_min}°C\n"
            message += f"Precipitacao: {precipitation} mm\n"
            message += f"{clothing_suggestion}\n"

        if "hourly" in weather_info:
            hourly = weather_info["hourly"]
            rain_hours = hourly.get("rain_hours", [])
            if rain_hours:
                rain_details = ", ".join(f"{h['hour']} ({h['rain']}mm)" for h in rain_hours)
                message += f"Chuva prevista: {rain_details}\n"
            else:
                message += "Sem previsao de chuva\n"

    return message
