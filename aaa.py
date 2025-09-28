import argparse
from datetime import datetime, timedelta
import requests
from notion_client import Client
import time

# -------------------------- 설정 --------------------------
SUBMIT_URL = "https://n8n.1000.school/webhook/0a43fbad-cc6d-4a5f-8727-b387c27de7c8"  # 교수님이 주신 URL (웹훅)
TEAM_ID = "3545f2b3-480d-4aed-8e7b-c9d4f2a46027"  # 우리 팀 ID
NOTION_DB_ID = "2739cd3a02218004bb5cc43ba0ac2523"
TEAM_MEMBERS = [
    {"notion_author_name": "조세연", "full_name": "조세연/물리학과", "user_email": "toma12345@gachon.ac.kr"},
    {"notion_author_name": "송민근", "full_name": "송민근/컴퓨터공학부(컴퓨터공학전공)", "user_email": "badugi2482@gachon.ac.kr"},
    {"notion_author_name": "이수성", "full_name": "이수성/미술·디자인학부(디자인)", "user_email": "lss040228@gachon.ac.kr"},
    {"notion_author_name": "김나현", "full_name": "김나현/AI·소프트웨어학부(소프트웨어전공)", "user_email": "nh5102@gachon.ac.kr"}
]
# -----------------------------------------------------------


# 마크다운 변환 로직
def rich_text_to_markdown(rich_text_array):
    md_text = ""
    for part in rich_text_array:
        content = part.get("plain_text", "")
        annotations = part.get("annotations", {})
        if annotations.get("bold"):
            content = f"**{content}**"
        if annotations.get("italic"):
            content = f"*{content}*"
        if annotations.get("strikethrough"):
            content = f"~~{content}~~"
        if annotations.get("code"):
            content = f"`{content}`"
        href = part.get("href")
        if href:
            content = f"[{content}]({href})"
        md_text += content
    return md_text


def blocks_to_markdown_recursive(notion, blocks, indent_level=0):
    markdown_lines = []
    indent = "    " * indent_level

    for block in blocks:
        block_type = block.get("type")

        # 제목 블록 앞에 공백 라인 추가
        if block_type in ["heading_1", "heading_2", "heading_3"]:
            if markdown_lines and markdown_lines[-1] != "":
                markdown_lines.append("")

        text = ""
        if block_type in ["heading_1", "heading_2", "heading_3", "paragraph", "bulleted_list_item", "numbered_list_item", "to_do"]:
            text = rich_text_to_markdown(block[block_type]["rich_text"])

        if block_type == "heading_1":
            markdown_lines.append(f"# {text}")
        elif block_type == "heading_2":
            markdown_lines.append(f"## {text}")
        elif block_type == "heading_3":
            markdown_lines.append(f"### {text}")
        elif block_type == "paragraph":
            is_pseudo_heading = text.startswith("**") and text.endswith("**")
            if is_pseudo_heading and markdown_lines and markdown_lines[-1] != "":
                markdown_lines.append("")
            markdown_lines.append(text)
        elif block_type == "bulleted_list_item":
            markdown_lines.append(f"{indent}* {text}")
        elif block_type == "numbered_list_item":
            markdown_lines.append(f"{indent}1. {text}")
        elif block_type == "to_do":
            prefix = "- [x]" if block["to_do"]["checked"] else "- [ ]"
            markdown_lines.append(f"{indent}{prefix} {text}")
        elif block_type == "divider":
            markdown_lines.append("---")

        if block.get("has_children"):
            child_blocks = notion.blocks.children.list(block_id=block["id"]).get("results", [])
            markdown_lines.append(blocks_to_markdown_recursive(notion, child_blocks, indent_level + 1))

    return "\n".join(markdown_lines)


def get_all_yesterday_entries(notion):
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"🔍 Notion에서 어제({yesterday_str}) 작성된 모든 항목을 찾습니다...")
    try:
        response = notion.databases.query(
            database_id=NOTION_DB_ID,
            filter={"property": "날짜", "date": {"equals": yesterday_str}}
        )

        entries = []
        for r in response.get("results", []):
            prop = r["properties"]
            page_id = r["id"]

            author_prop = prop.get("작성자", {}).get("people", [{}])
            author_name = author_prop[0].get("name", "") if author_prop else ""

            if author_name and page_id:
                top_level_blocks = notion.blocks.children.list(block_id=page_id).get("results", [])
                page_content_md = blocks_to_markdown_recursive(notion, top_level_blocks)

                if page_content_md:
                    entries.append({"author": author_name, "content": page_content_md})
        return entries
    except Exception as e:
        print(f"❌ Notion 데이터 조회 중 오류 발생: {e}")
        return []


def send_single_snippet(snippet_object):
    author_name = snippet_object["full_name"]
    print(f"\n🚀 '{author_name}' 님의 스니펫을 [POST]로 전송합니다...")

    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    params = {"api_id": TEAM_ID, "date_from": yesterday_str, "date_to": yesterday_str}
    payload = snippet_object

    try:
        res = requests.post(SUBMIT_URL, params=params, json=payload)
        if res.status_code >= 400:
            print(f"    ⚠️  '{author_name}' 님 스니펫 전송 결과: 서버가 요청을 거부했습니다 (HTTP {res.status_code})")
            print("      📄 이유:", res.json().get("detail", res.text))
        else:
            print(f"    ✅ '{author_name}' 님 스니펫 전송 성공!")
            if res.text:
                print("      📄 서버 응답: (성공)")
    except requests.exceptions.RequestException as e:
        print(f"    ❌ 통신 오류 발생: {e}")


def main():
    parser = argparse.ArgumentParser(description="Notion DB의 어제 항목들의 '내용'을 Daily Snippet으로 전송합니다.")
    parser.add_argument("--token", required=True, help="Notion Integration Token")
    args = parser.parse_args()
    notion = Client(auth=args.token)
    all_entries = get_all_yesterday_entries(notion)

    if not all_entries:
        print("\n🚫 처리 완료: 어제 Notion에 작성된 글이 없거나 내용을 가져올 수 없었습니다.")
        return

    print(f"\n👍 Notion에서 총 {len(all_entries)}개의 항목을 찾았습니다. 팀원별로 전송을 시작합니다.")

    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    for member in TEAM_MEMBERS:
        member_entry = next((entry for entry in all_entries if entry["author"] == member["notion_author_name"]), None)

        if not member_entry:
            continue

        content = member_entry["content"]

        snippet_object = {
            "user_email": member["user_email"],
            "api_id": TEAM_ID,
            "snippet_date": yesterday_str,
            "content": content,
            "team_name": "7기-1팀",
            "full_name": member["full_name"],
        }
        send_single_snippet(snippet_object)
        time.sleep(1)


if __name__ == "__main__":
    main()
