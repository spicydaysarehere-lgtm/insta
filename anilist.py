import requests

URL = "https://graphql.anilist.co"
QUERY = """
query($page:Int,$perPage:Int,$genres:[String],$sort:[MediaSort],$score:Int){
  Page(page:$page,perPage:$perPage){
    media(
      type:ANIME
      genre_in:$genres
      averageScore_greater:$score
      sort:$sort
    ){
      id
      title { romaji english native }
      genres
      averageScore
      popularity
      episodes
      duration
      status
      format
      isAdult
      siteUrl
    }
  }
}
"""


def get_matching_anime(genres, minimum_score=0, per_page=50):
    wanted = {g.strip().casefold() for g in genres if g.strip()}
    if not wanted:
        raise ValueError("No genres supplied")

    response = requests.post(
        URL,
        json={
            "query": QUERY,
            "variables": {
                "page": 1,
                "perPage": min(per_page, 50),
                "genres": list(wanted),
                "sort": ["POPULARITY_DESC", "SCORE_DESC"],
                "score": int(minimum_score),
            },
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])

    result = []
    for anime in payload["data"]["Page"]["media"]:
        actual = {x.casefold() for x in anime.get("genres", [])}
        # Explicit ALL matching: every requested genre must be present.
        if wanted.issubset(actual):
            result.append(anime)
    return result
