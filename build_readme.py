from python_graphql_client import GraphqlClient
import feedparser
import httpx
import json
import pathlib
import re
import os

root = pathlib.Path(__file__).parent.resolve()
client = GraphqlClient(endpoint="https://api.github.com/graphql")


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def replace_chunk(content, marker, chunk, inline=False):
    r = re.compile(
        r"<!\-\- {} starts \-\->.*<!\-\- {} ends \-\->".format(marker, marker),
        re.DOTALL,
    )
    if not inline:
        chunk = "\n{}\n".format(chunk)
    chunk = "<!-- {} starts -->{}<!-- {} ends -->".format(marker, chunk, marker)
    return r.sub(chunk, content)


def make_recent_contributions_query(after_cursor=None):
    return """
query {
  viewer {
    repositoriesContributedTo(privacy: PUBLIC, includeUserRepositories: true, first: 100, after: AFTER) {
      pageInfo {
        hasNextPage
        endCursor
      }
      totalCount
      nodes {
        nameWithOwner
        url
        updatedAt
        description
      }
    }
  }
}
""".replace(
        "AFTER", '"{}"'.format(after_cursor) if after_cursor else "null"
    )


def fetch_recent_contributions(oauth_token):
    recent_contributions = []
    has_next_page = True
    after_cursor = None

    while has_next_page:
        data = client.execute(
            query=make_recent_contributions_query(after_cursor),
            headers={"Authorization": "Bearer {}".format(oauth_token)},
        )
        print()
        print(json.dumps(data, indent=4))
        print()
        for repo in data["data"]["viewer"]["repositoriesContributedTo"]["nodes"]:
            if repo["nameWithOwner"] == "M157q/M157q":
                continue

            recent_contributions.append(
                {
                    "repo": repo["nameWithOwner"],
                    "repo_url": repo["url"],
                    "description": repo["description"],
                    "updated_at": repo["updatedAt"].split("T")[0],
                }
            )
        has_next_page = data["data"]["viewer"]["repositoriesContributedTo"]["pageInfo"][
            "hasNextPage"
        ]
        after_cursor = data["data"]["viewer"]["repositoriesContributedTo"]["pageInfo"]["endCursor"]
    return recent_contributions


def fetch_tils(oauth_token):
    query = """
	query {
	  viewer {
	    repository(name: "m157q.github.io") {
	      issues(filterBy: {createdBy: "M157q", states: OPEN}, orderBy: {field: UPDATED_AT, direction: DESC}, first: 5, states: OPEN) {
		nodes {
		  url
		  updatedAt
		  title
		}
	      }
	    }
	  }
	}
    """
    data = client.execute(
	query=query,
	headers={"Authorization": "Bearer {}".format(oauth_token)},
    )
    print()
    print(json.dumps(data, indent=4))
    print()

    tils = []
    for til in data["data"]["viewer"]["repository"]["issues"]["nodes"]:
        tils.append(
            {
                "title": til["title"],
                "url": til["url"],
                "updated_at": til["updatedAt"],
            }
        )

    return tils


def fetch_blog_entries():
    entries = feedparser.parse("https://blog.m157q.tw/feeds/category.note.atom.xml")["entries"]
    return [
        {
            "title": entry["title"],
            "url": entry["link"].split("#")[0],
            "published": entry["published"].split("T")[0],
        }
        for entry in entries
    ]


if __name__ == "__main__":
    readme = root / "README.md"
    project_recent_contributions = root / "recent_contributions.md"
    recent_contributions = fetch_recent_contributions(GITHUB_TOKEN)
    recent_contributions.sort(key=lambda r: r["updated_at"], reverse=True)
    md = "\n".join(
        [
            "* [{repo}]({repo_url}) - {updated_at}".format(**recent_contribution)
            for recent_contribution in recent_contributions[:5]
        ]
    )
    readme_contents = readme.open().read()
    rewritten = replace_chunk(readme_contents, "recent_contributions", md)

    # Write out full project-recent_contributions.md file
    project_recent_contributions_md = "\n".join(
        [
            (
                "* **[{repo}]({repo_url})** - {updated_at}\n"
                "<br>{description}"
            ).format(**recent_contribution)
            for recent_contribution in recent_contributions
        ]
    )
    project_recent_contributions_content = project_recent_contributions.open().read()
    project_recent_contributions_content = replace_chunk(
        project_recent_contributions_content, "recent_contributions", project_recent_contributions_md
    )
    project_recent_contributions_content = replace_chunk(
        project_recent_contributions_content, "recent_contributions_count", str(len(recent_contributions)), inline=True
    )
    project_recent_contributions.open("w").write(project_recent_contributions_content)

    # Fetch TILs
    tils = fetch_tils(GITHUB_TOKEN)
    tils_md = "\n".join(
        [
            "* [{title}]({url}) - {updated_at}".format(
                title=til["title"],
                url=til["url"],
                updated_at=til["updated_at"].split("T")[0],
            )
            for til in tils
        ]
    )
    rewritten = replace_chunk(rewritten, "tils", tils_md)

    # Fetch blog entries
    entries = fetch_blog_entries()[:5]
    entries_md = "\n".join(
        ["* [{title}]({url}) - {published}".format(**entry) for entry in entries]
    )
    rewritten = replace_chunk(rewritten, "blog", entries_md)

    readme.open("w").write(rewritten)
