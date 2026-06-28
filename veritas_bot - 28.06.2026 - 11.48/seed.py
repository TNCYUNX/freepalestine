import database
import json

def force_seed():
    print("Veritabanı zorunlu tohumlama başlatılıyor...")
    try:
        conn = database.get_db_connection()
        cursor = conn.cursor()
        
        # Masayı temizle ve yeniden kur
        cursor.execute("DROP TABLE IF EXISTS api_countries")
        cursor.execute("CREATE TABLE api_countries (country_code VARCHAR(10) PRIMARY KEY, country_name VARCHAR(100), flag VARCHAR(10))")
        
        ulkeler = [
            {"code": "0", "name": "Russia", "flag": "🇷🇺"},
            {"code": "74", "name": "Afghanistan", "flag": "🇦🇫"}, {"code": "155", "name": "Albania", "flag": "🇦🇱"},
            {"code": "58", "name": "Algeria", "flag": "🇩🇿"}, {"code": "76", "name": "Angola", "flag": "🇦🇴"},
            {"code": "181", "name": "Anguilla", "flag": "🇦🇮"}, {"code": "39", "name": "Argentina", "flag": "🇦🇷"},
            {"code": "148", "name": "Armenia", "flag": "🇦🇲"}, {"code": "179", "name": "Aruba", "flag": "🇦🇼"},
            {"code": "175", "name": "Australia", "flag": "🇦🇺"}, {"code": "50", "name": "Austria", "flag": "🇦🇹"},
            {"code": "35", "name": "Azerbaijan", "flag": "🇦🇿"}, {"code": "122", "name": "Bahamas", "flag": "🇧🇸"},
            {"code": "145", "name": "Bahrain", "flag": "🇧🇭"}, {"code": "60", "name": "Bangladesh", "flag": "🇧🇩"},
            {"code": "118", "name": "Barbados", "flag": "🇧🇧"}, {"code": "51", "name": "Belarus", "flag": "🇧🇾"},
            {"code": "82", "name": "Belgium", "flag": "🇧🇪"}, {"code": "124", "name": "Belize", "flag": "🇧🇿"},
            {"code": "120", "name": "Benin", "flag": "🇧🇯"}, {"code": "158", "name": "Bhutan", "flag": "🇧🇹"},
            {"code": "92", "name": "Bolivia", "flag": "🇧🇴"}, {"code": "108", "name": "Bosnia and Herzegovina", "flag": "🇧🇦"},
            {"code": "123", "name": "Botswana", "flag": "🇧🇼"}, {"code": "73", "name": "Brazil", "flag": "🇧🇷"},
            {"code": "121", "name": "Brunei Darussalam", "flag": "🇧🇳"}, {"code": "83", "name": "Bulgaria", "flag": "🇧🇬"},
            {"code": "119", "name": "Burundi", "flag": "🇧🇮"}, {"code": "24", "name": "Cambodia", "flag": "🇰🇭"},
            {"code": "41", "name": "Cameroon", "flag": "🇨🇲"}, {"code": "36", "name": "Canada", "flag": "🇨🇦"},
            {"code": "186", "name": "Cape Verde", "flag": "🇨🇻"}, {"code": "170", "name": "Cayman islands", "flag": "🇰🇾"},
            {"code": "42", "name": "Chad", "flag": "🇹🇩"}, {"code": "151", "name": "Chile", "flag": "🇨🇱"},
            {"code": "3", "name": "China", "flag": "🇨🇳"}, {"code": "33", "name": "Colombia", "flag": "🇨🇴"},
            {"code": "133", "name": "Comoros", "flag": "🇰🇲"}, {"code": "93", "name": "Costa Rica", "flag": "🇨🇷"},
            {"code": "45", "name": "Croatia", "flag": "🇭🇷"}, {"code": "77", "name": "Cyprus", "flag": "🇨🇾"},
            {"code": "63", "name": "Czech Republic", "flag": "🇨🇿"}, {"code": "18", "name": "DR Congo", "flag": "🇨🇩"},
            {"code": "172", "name": "Denmark", "flag": "🇩🇰"}, {"code": "168", "name": "Djibouti", "flag": "🇩🇯"},
            {"code": "126", "name": "Dominica", "flag": "🇩🇲"}, {"code": "109", "name": "Dominican Republic", "flag": "🇩🇴"},
            {"code": "105", "name": "Ecuador", "flag": "🇪🇨"}, {"code": "21", "name": "Egypt", "flag": "🇪🇬"},
            {"code": "167", "name": "Equatorial Guinea", "flag": "🇬🇶"}, {"code": "176", "name": "Eritrea", "flag": "🇪🇷"},
            {"code": "34", "name": "Estonia", "flag": "🇪🇪"}, {"code": "71", "name": "Ethiopia", "flag": "🇪🇹"},
            {"code": "163", "name": "Finland", "flag": "🇫🇮"}, {"code": "78", "name": "France", "flag": "🇫🇷"},
            {"code": "162", "name": "French Guiana", "flag": "🇬🇫"}, {"code": "1012", "name": "French Polynesia", "flag": "🇵🇫"},
            {"code": "154", "name": "Gabon", "flag": "🇬🇦"}, {"code": "28", "name": "Gambia", "flag": "🇬🇲"},
            {"code": "128", "name": "Georgia", "flag": "🇬🇪"}, {"code": "38", "name": "Ghana", "flag": "🇬🇭"},
            {"code": "129", "name": "Greece", "flag": "🇬🇷"}, {"code": "127", "name": "Grenada", "flag": "🇬🇩"},
            {"code": "160", "name": "Guadeloupe", "flag": "🇬🇵"}, {"code": "94", "name": "Guatemala", "flag": "🇬🇹"},
            {"code": "68", "name": "Guinea", "flag": "🇬🇳"}, {"code": "130", "name": "Guinea-Bissau", "flag": "🇬🇼"},
            {"code": "131", "name": "Guyana", "flag": "🇬🇾"}, {"code": "26", "name": "Haiti", "flag": "🇭🇹"},
            {"code": "14", "name": "Hong Kong", "flag": "🇭🇰"}, {"code": "84", "name": "Hungary", "flag": "🇭🇺"},
            {"code": "132", "name": "Iceland", "flag": "🇮🇸"}, {"code": "22", "name": "India", "flag": "🇮🇳"},
            {"code": "6", "name": "Indonesia", "flag": "🇮🇩"}, {"code": "10016", "name": "Iran", "flag": "🇮🇷"},
            {"code": "47", "name": "Iraq", "flag": "🇮🇶"}, {"code": "23", "name": "Ireland", "flag": "🇮🇪"},
            {"code": "13", "name": "Israel", "flag": "🇮🇱"}, {"code": "86", "name": "Italy", "flag": "🇮🇹"},
            {"code": "103", "name": "Jamaica", "flag": "🇯🇲"}, {"code": "116", "name": "Jordan", "flag": "🇯🇴"},
            {"code": "2", "name": "Kazakhstan", "flag": "🇰🇿"}, {"code": "8", "name": "Kenya", "flag": "🇰🇪"},
            {"code": "100", "name": "Kuwait", "flag": "🇰🇼"}, {"code": "11", "name": "Kyrgyzstan", "flag": "🇰🇬"},
            {"code": "49", "name": "Latvia", "flag": "🇱🇻"}, {"code": "153", "name": "Lebanon", "flag": "🇱🇧"},
            {"code": "136", "name": "Lesotho", "flag": "🇱🇸"}, {"code": "135", "name": "Liberia", "flag": "🇱🇷"},
            {"code": "102", "name": "Libya", "flag": "🇱🇾"}, {"code": "44", "name": "Lithuania", "flag": "🇱🇹"},
            {"code": "165", "name": "Luxembourg", "flag": "🇱🇺"}, {"code": "20", "name": "Macao", "flag": "🇲🇴"},
            {"code": "137", "name": "Malawi", "flag": "🇲🇼"}, {"code": "159", "name": "Maldives", "flag": "🇲🇻"},
            {"code": "69", "name": "Mali", "flag": "🇲🇱"}, {"code": "114", "name": "Mauritania", "flag": "🇲🇷"},
            {"code": "157", "name": "Mauritius", "flag": "🇲🇺"}, {"code": "54", "name": "Mexico", "flag": "🇲🇽"},
            {"code": "85", "name": "Moldova", "flag": "🇲🇩"}, {"code": "144", "name": "Monaco", "flag": "🇲🇨"},
            {"code": "72", "name": "Mongolia", "flag": "🇲🇳"}, {"code": "171", "name": "Montenegro", "flag": "🇲🇪"},
            {"code": "180", "name": "Montserrat", "flag": "🇲🇸"}, {"code": "37", "name": "Morocco", "flag": "🇲🇦"},
            {"code": "80", "name": "Mozambique", "flag": "🇲🇿"}, {"code": "5", "name": "Myanmar", "flag": "🇲🇲"},
            {"code": "138", "name": "Namibia", "flag": "🇳🇦"}, {"code": "48", "name": "Netherlands", "flag": "🇳🇱"},
            {"code": "185", "name": "New Caledonia", "flag": "🇳🇨"}, {"code": "67", "name": "New Zealand", "flag": "🇳🇿"},
            {"code": "90", "name": "Nicaragua", "flag": "🇳🇮"}, {"code": "139", "name": "Niger", "flag": "🇳🇪"},
            {"code": "19", "name": "Nigeria", "flag": "🇳🇬"}, {"code": "183", "name": "North Macedonia", "flag": "🇲🇰"},
            {"code": "107", "name": "Oman", "flag": "🇴🇲"}, {"code": "66", "name": "Pakistan", "flag": "🇵🇰"},
            {"code": "112", "name": "Panama", "flag": "🇵🇦"}, {"code": "87", "name": "Paraguay", "flag": "🇵🇾"},
            {"code": "65", "name": "Peru", "flag": "🇵🇪"}, {"code": "4", "name": "Philippines", "flag": "🇵🇭"},
            {"code": "15", "name": "Poland", "flag": "🇵🇱"}, {"code": "117", "name": "Portugal", "flag": "🇵🇹"},
            {"code": "97", "name": "Puerto Rico", "flag": "🇵🇷"}, {"code": "111", "name": "Qatar", "flag": "🇶🇦"},
            {"code": "150", "name": "Republic of the Congo", "flag": "🇨🇬"}, {"code": "146", "name": "Reunion", "flag": "🇷🇪"},
            {"code": "32", "name": "Romania", "flag": "🇷🇴"}, {"code": "140", "name": "Rwanda", "flag": "🇷🇼"},
            {"code": "134", "name": "Saint Kitts and Nevis", "flag": "🇰🇳"}, {"code": "164", "name": "Saint Lucia", "flag": "🇱🇨"},
            {"code": "166", "name": "Saint Vincent", "flag": "🇻🇨"}, {"code": "101", "name": "Salvador", "flag": "🇸🇻"},
            {"code": "178", "name": "Sao Tome and Principe", "flag": "🇸🇹"}, {"code": "53", "name": "Saudi Arabia", "flag": "🇸🇦"},
            {"code": "61", "name": "Senegal", "flag": "🇸🇳"}, {"code": "29", "name": "Serbia", "flag": "🇷🇸"},
            {"code": "184", "name": "Seychelles", "flag": "🇸🇨"}, {"code": "115", "name": "Sierra Leone", "flag": "🇸🇱"},
            {"code": "10351", "name": "Singapore", "flag": "🇸🇬"}, {"code": "141", "name": "Slovakia", "flag": "🇸🇰"},
            {"code": "59", "name": "Slovenia", "flag": "🇸🇮"}, {"code": "149", "name": "Somalia", "flag": "🇸🇴"},
            {"code": "31", "name": "South Africa", "flag": "🇿🇦"}, {"code": "10350", "name": "South Korea", "flag": "🇰🇷"},
            {"code": "64", "name": "Sri Lanka", "flag": "🇱🇰"}, {"code": "142", "name": "Suriname", "flag": "🇸🇷"},
            {"code": "55", "name": "Taiwan", "flag": "🇹🇼"}, {"code": "143", "name": "Tajikistan", "flag": "🇹🇯"},
            {"code": "9", "name": "Tanzania", "flag": "🇹🇿"}, {"code": "91", "name": "Timor-Leste", "flag": "🇹🇱"},
            {"code": "99", "name": "Togo", "flag": "🇹🇬"}, {"code": "104", "name": "Trinidad and Tobago", "flag": "🇹🇹"},
            {"code": "89", "name": "Tunisia", "flag": "🇹🇳"}, {"code": "161", "name": "Turkmenistan", "flag": "🇹🇲"},
            {"code": "187", "name": "USA", "flag": "🇺🇸"}, {"code": "75", "name": "Uganda", "flag": "🇺🇬"},
            {"code": "1", "name": "Ukraine", "flag": "🇺🇦"}, {"code": "95", "name": "United Arab Emirates", "flag": "🇦🇪"},
            {"code": "16", "name": "United Kingdom", "flag": "🇬🇧"}, {"code": "156", "name": "Uruguay", "flag": "🇺🇾"},
            {"code": "40", "name": "Uzbekistan", "flag": "🇺🇿"}, {"code": "70", "name": "Venezuela", "flag": "🇻🇪"},
            {"code": "10", "name": "Vietnam", "flag": "🇻🇳"}, {"code": "30", "name": "Yemen", "flag": "🇾🇪"},
            {"code": "147", "name": "Zambia", "flag": "🇿🇲"}, {"code": "96", "name": "Zimbabwe", "flag": "🇿🇼"},
            {"code": "10161", "name": "American Samoa", "flag": "🇦🇸"}, {"code": "1062", "name": "Andorra", "flag": "🇦🇩"},
            {"code": "169", "name": "Antigua and Barbuda", "flag": "🇦🇬"}, {"code": "1003", "name": "Bermuda", "flag": "🇧🇲"},
            {"code": "152", "name": "Burkina Faso", "flag": "🇧🇫"}, {"code": "125", "name": "Central African Republic", "flag": "🇨🇫"},
            {"code": "113", "name": "Cuba", "flag": "🇨🇺"}, {"code": "189", "name": "Fiji", "flag": "🇫🇯"},
            {"code": "43", "name": "Germany", "flag": "🇩🇪"}, {"code": "201", "name": "Gibraltar", "flag": "🇬🇮"},
            {"code": "1008", "name": "Greenland", "flag": "🇬🇱"}, {"code": "88", "name": "Honduras", "flag": "🇭🇳"},
            {"code": "27", "name": "Ivory Coast", "flag": "🇨🇮"}, {"code": "182", "name": "Japan", "flag": "🇯🇵"},
            {"code": "203", "name": "Kosovo", "flag": "🇽🇰"}, {"code": "25", "name": "Laos", "flag": "🇱🇦"},
            {"code": "10348", "name": "Liechtenstein", "flag": "🇱🇮"}, {"code": "17", "name": "Madagascar", "flag": "🇲🇬"},
            {"code": "7", "name": "Malaysia", "flag": "🇲🇾"}, {"code": "199", "name": "Malta", "flag": "🇲🇹"},
            {"code": "1011", "name": "Martinique", "flag": "🇲🇶"}, {"code": "81", "name": "Nepal", "flag": "🇳🇵"},
            {"code": "204", "name": "Niue", "flag": "🇳🇺"}, {"code": "174", "name": "Norway", "flag": "🇳🇴"},
            {"code": "188", "name": "Palestine", "flag": "🇵🇸"}, {"code": "79", "name": "Papua New Guinea", "flag": "🇵🇬"},
            {"code": "10231", "name": "Samoa", "flag": "🇼🇸"}, {"code": "10349", "name": "Sint Maarten", "flag": "🇸🇽"},
            {"code": "177", "name": "South Sudan", "flag": "🇸🇸"}, {"code": "56", "name": "Spain", "flag": "🇪🇸"},
            {"code": "106", "name": "Swaziland", "flag": "🇸🇿"}, {"code": "46", "name": "Sweden", "flag": "🇸🇪"},
            {"code": "173", "name": "Switzerland", "flag": "🇨🇭"}, {"code": "110", "name": "Syria", "flag": "🇸🇾"},
            {"code": "52", "name": "Thailand", "flag": "🇹🇭"}, {"code": "10227", "name": "Tonga", "flag": "🇹🇴"},
            {"code": "62", "name": "Turkey", "flag": "🇹🇷"}, {"code": "12", "name": "USA (virtual)", "flag": "🇺🇸"},
            {"code": "1007", "name": "Vanuatu", "flag": "🇻🇺"}
        ]
        
        for u in ulkeler:
            cursor.execute("INSERT INTO api_countries (country_code, country_name, flag) VALUES (%s, %s, %s)", (u['code'], u['name'], u['flag']))
        
        conn.commit()
        print(f"Başarılı! {len(ulkeler)} ülke veritabanına eklendi.")
        conn.close()
    except Exception as e:
        print(f"Hata: {e}")

if __name__ == "__main__":
    force_seed()
