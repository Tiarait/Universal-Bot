import asyncio
import os
import io
import tempfile

from moviepy import AudioFileClip
from moviepy.video.io.VideoFileClip import VideoFileClip

TMP_DIR = os.path.join(".temp")

async def video_to_clip_bytes(video_bytes: bytes, name: str = None) -> io.BytesIO:
    loop = asyncio.get_event_loop()
    out_buffer = io.BytesIO()

    def _process_video(tmp_video_path: str):
        with VideoFileClip(tmp_video_path) as clip:
            min_side = min(clip.w, clip.h)
            scale_factor = 360 / min_side
            clip_resized = clip.resized(scale_factor)

            size = min(clip_resized.w, clip_resized.h)
            x_center = clip_resized.w / 2
            y_center = clip_resized.h / 2
            clip_cropped = clip_resized.cropped(x_center=x_center, y_center=y_center, width=size, height=size)

            if clip_cropped.duration > 60:
                clip_cropped = clip_cropped.subclipped(0, 60)

            with tempfile.NamedTemporaryFile(dir=TMP_DIR, suffix=".mp4", delete=True) as tmp_out:
                clip_cropped.write_videofile(
                    tmp_out.name,
                    codec="libx264",
                    audio_codec="aac",
                    write_logfile=False
                )
                tmp_out.seek(0)
                out_buffer.write(tmp_out.read())

        out_buffer.seek(0)

    with tempfile.NamedTemporaryFile(dir=TMP_DIR, suffix=".mp4", delete=True) as tmp_video:
        tmp_video.write(video_bytes)
        tmp_video.flush()
        await loop.run_in_executor(None, _process_video, tmp_video.name)

    if not name:
        name = "clip"
    out_buffer.name = f"{name}.mp4"
    return out_buffer


async def audio_as_voice(video_bytes: bytes, name: str = None) -> io.BytesIO:
    loop = asyncio.get_event_loop()
    out_buffer = io.BytesIO()

    def _process(tmp_path: str):
        with AudioFileClip(tmp_path) as clip:
            with tempfile.NamedTemporaryFile(dir=TMP_DIR, suffix=".ogg", delete=True) as tmp_out:
                clip.write_audiofile(
                    tmp_out.name,
                    codec="libopus",
                    ffmpeg_params=["-ac", "1", "-ar", "48000", "-b:a", "64k"]
                )
                tmp_out.seek(0)
                out_buffer.write(tmp_out.read())

        out_buffer.seek(0)

    with tempfile.NamedTemporaryFile(dir=TMP_DIR, suffix=".mp3", delete=True) as tmp_:
        tmp_.write(video_bytes)
        tmp_.flush()
        await loop.run_in_executor(None, _process, tmp_.name)

    if not name: name = "voice"
    out_buffer.name = f"{name}.ogg"
    return out_buffer


country_codes = {
    "1": "🇺🇸 USA",
    "7": "🇷🇺 Russia",
    "20": "🇪🇬 Egypt",
    "27": "🇿🇦 South Africa",
    "30": "🇬🇷 Greece",
    "31": "🇳🇱 Netherlands",
    "32": "🇧🇪 Belgium",
    "33": "🇫🇷 France",
    "34": "🇪🇸 Spain",
    "36": "🇭🇺 Hungary",
    "39": "🇮🇹 Italy",
    "40": "🇷🇴 Romania",
    "41": "🇨🇭 Switzerland",
    "43": "🇦🇹 Austria",
    "44": "🇬🇧 UK",
    "45": "🇩🇰 Denmark",
    "46": "🇸🇪 Sweden",
    "47": "🇳🇴 Norway",
    "48": "🇵🇱 Poland",
    "49": "🇩🇪 Germany",
    "51": "🇵🇪 Peru",
    "52": "🇲🇽 Mexico",
    "53": "🇨🇺 Cuba",
    "54": "🇦🇷 Argentina",
    "55": "🇧🇷 Brazil",
    "56": "🇨🇱 Chile",
    "57": "🇨🇴 Colombia",
    "58": "🇻🇪 Venezuela",
    "60": "🇲🇾 Malaysia",
    "61": "🇦🇺 Australia",
    "62": "🇮🇩 Indonesia",
    "63": "🇵🇭 Philippines",
    "64": "🇳🇿 New Zealand",
    "65": "🇸🇬 Singapore",
    "66": "🇹🇭 Thailand",
    "81": "🇯🇵 Japan",
    "82": "🇰🇷 South Korea",
    "84": "🇻🇳 Vietnam",
    "86": "🇨🇳 China",
    "90": "🇹🇷 Turkey",
    "91": "🇮🇳 India",
    "92": "🇵🇰 Pakistan",
    "93": "🇦🇫 Afghanistan",
    "94": "🇱🇰 Sri Lanka",
    "95": "🇲🇲 Myanmar",
    "98": "🇮🇷 Iran",
    "212": "🇲🇦 Morocco",
    "213": "🇩🇿 Algeria",
    "216": "🇹🇳 Tunisia",
    "218": "🇱🇾 Libya",
    "220": "🇬🇲 Gambia",
    "221": "🇸🇳 Senegal",
    "222": "🇲🇷 Mauritania",
    "223": "🇲🇱 Mali",
    "224": "🇬🇳 Guinea",
    "225": "🇨🇮 Ivory Coast",
    "226": "🇧🇫 Burkina Faso",
    "227": "🇳🇪 Niger",
    "228": "🇹🇬 Togo",
    "229": "🇧🇯 Benin",
    "230": "🇲🇺 Mauritius",
    "231": "🇱🇷 Liberia",
    "232": "🇸🇱 Sierra Leone",
    "233": "🇬🇭 Ghana",
    "234": "🇳🇬 Nigeria",
    "235": "🇹🇩 Chad",
    "236": "🇨🇫 Central African Republic",
    "237": "🇨🇲 Cameroon",
    "238": "🇨🇻 Cape Verde",
    "239": "🇸🇹 Sao Tome and Principe",
    "240": "🇬🇶 Equatorial Guinea",
    "241": "🇬🇦 Gabon",
    "242": "🇨🇬 Republic of the Congo",
    "243": "🇨🇩 DR Congo",
    "244": "🇦🇴 Angola",
    "245": "🇬🇼 Guinea-Bissau",
    "246": "🇮🇴 British Indian Ocean Territory",
    "248": "🇸🇨 Seychelles",
    "249": "🇸🇩 Sudan",
    "250": "🇷🇼 Rwanda",
    "251": "🇪🇹 Ethiopia",
    "252": "🇸🇴 Somalia",
    "253": "🇩🇯 Djibouti",
    "254": "🇰🇪 Kenya",
    "255": "🇹🇿 Tanzania",
    "256": "🇺🇬 Uganda",
    "257": "🇧🇮 Burundi",
    "258": "🇲🇿 Mozambique",
    "260": "🇿🇲 Zambia",
    "261": "🇲🇬 Madagascar",
    "262": "🇷🇪 Reunion",
    "263": "🇿🇼 Zimbabwe",
    "264": "🇳🇦 Namibia",
    "265": "🇲🇼 Malawi",
    "266": "🇱🇸 Lesotho",
    "267": "🇧🇼 Botswana",
    "268": "🇸🇿 Eswatini",
    "269": "🇰🇲 Comoros",
    "290": "🇸🇭 Saint Helena",
    "291": "🇪🇷 Eritrea",
    "297": "🇦🇼 Aruba",
    "298": "🇫🇴 Faroe Islands",
    "299": "🇬🇱 Greenland",
    "350": "🇬🇮 Gibraltar",
    "351": "🇵🇹 Portugal",
    "352": "🇱🇺 Luxembourg",
    "353": "🇮🇪 Ireland",
    "354": "🇮🇸 Iceland",
    "355": "🇦🇱 Albania",
    "356": "🇲🇹 Malta",
    "357": "🇨🇾 Cyprus",
    "358": "🇫🇮 Finland",
    "359": "🇧🇬 Bulgaria",
    "370": "🇱🇹 Lithuania",
    "371": "🇱🇻 Latvia",
    "372": "🇪🇪 Estonia",
    "373": "🇲🇩 Moldova",
    "374": "🇦🇲 Armenia",
    "375": "🇧🇾 Belarus",
    "376": "🇦🇩 Andorra",
    "377": "🇲🇨 Monaco",
    "378": "🇸🇲 San Marino",
    "380": "🇺🇦 Ukraine",
    "381": "🇷🇸 Serbia",
    "382": "🇲🇪 Montenegro",
    "383": "🇽🇰 Kosovo",
    "385": "🇭🇷 Croatia",
    "386": "🇸🇮 Slovenia",
    "387": "🇧🇦 Bosnia and Herzegovina",
    "389": "🇲🇰 North Macedonia",
    "420": "🇨🇿 Czech Republic",
    "421": "🇸🇰 Slovakia",
    "423": "🇱🇮 Liechtenstein",
    "500": "🇫🇰 Falkland Islands",
    "501": "🇧🇿 Belize",
    "502": "🇬🇹 Guatemala",
    "503": "🇸🇻 El Salvador",
    "504": "🇭🇳 Honduras",
    "505": "🇳🇮 Nicaragua",
    "506": "🇨🇷 Costa Rica",
    "507": "🇵🇦 Panama",
    "508": "🇵🇲 Saint Pierre and Miquelon",
    "509": "🇭🇹 Haiti",
    "590": "🇬🇵 Guadeloupe",
    "591": "🇧🇴 Bolivia",
    "592": "🇬🇾 Guyana",
    "593": "🇪🇨 Ecuador",
    "594": "🇬🇫 French Guiana",
    "595": "🇵🇾 Paraguay",
    "596": "🇲🇶 Martinique",
    "597": "🇸🇷 Suriname",
    "598": "🇺🇾 Uruguay",
    "599": "🇨🇼 Curacao",
    "670": "🇹🇱 East Timor",
    "672": "🇳🇫 Norfolk Island",
    "673": "🇧🇳 Brunei",
    "674": "🇳🇷 Nauru",
    "675": "🇵🇬 Papua New Guinea",
    "676": "🇹🇴 Tonga",
    "677": "🇸🇧 Solomon Islands",
    "678": "🇻🇺 Vanuatu",
    "679": "🇫🇯 Fiji",
    "680": "🇵🇼 Palau",
    "681": "🇼🇫 Wallis and Futuna",
    "682": "🇨🇰 Cook Islands",
    "683": "🇳🇺 Niue",
    "685": "🇼🇸 Samoa",
    "686": "🇰🇮 Kiribati",
    "687": "🇳🇨 New Caledonia",
    "688": "🇹🇻 Tuvalu",
    "689": "🇵🇫 French Polynesia",
    "690": "🇹🇰 Tokelau",
    "691": "🇫🇲 Micronesia",
    "692": "🇲🇭 Marshall Islands",
    "850": "🇰🇵 North Korea",
    "852": "🇭🇰 Hong Kong",
    "853": "🇲🇴 Macau",
    "855": "🇰🇭 Cambodia",
    "856": "🇱🇦 Laos",
    "880": "🇧🇩 Bangladesh",
    "886": "🇹🇼 Taiwan",
    "960": "🇲🇻 Maldives",
    "961": "🇱🇧 Lebanon",
    "962": "🇯🇴 Jordan",
    "963": "🇸🇾 Syria",
    "964": "🇮🇶 Iraq",
    "965": "🇰🇼 Kuwait",
    "966": "🇸🇦 Saudi Arabia",
    "967": "🇾🇪 Yemen",
    "968": "🇴🇲 Oman",
    "970": "🇵🇸 Palestine",
    "971": "🇦🇪 UAE",
    "972": "🇮🇱 Israel",
    "973": "🇧🇭 Bahrain",
    "974": "🇶🇦 Qatar",
    "975": "🇧🇹 Bhutan",
    "976": "🇲🇳 Mongolia",
    "977": "🇳🇵 Nepal",
    "992": "🇹🇯 Tajikistan",
    "993": "🇹🇲 Turkmenistan",
    "994": "🇦🇿 Azerbaijan",
    "995": "🇬🇪 Georgia",
    "996": "🇰🇬 Kyrgyzstan",
    "998": "🇺🇿 Uzbekistan"
}


def get_country(phone_number: str) -> str:
    if not phone_number.startswith("+") and len(phone_number) != 12:
        return ""
    if phone_number.startswith("+"):
        digits = phone_number[1:]
    else:
        digits = phone_number
    for code_length in range(4, 0, -1):
        code = digits[:code_length]
        if code in country_codes:
            return country_codes[code]
    return