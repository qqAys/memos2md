# -*- coding: utf-8 -*-
"""
File: memos2md.py
Author: Jinx
Email: me@qqays.xyz
Github: https://github.com/qqAys/memos2md
Description: This is a Python script for converting memos into Markdown format, handling attachment links and file structure.
"""

import datetime
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

memos2md = "memos2md"
script_author = "Jinx <me@qqays.xyz>"
github_url = f"https://github.com/qqAys/{memos2md}"

you_like_it = False


class Fetch:
    ONE = "fetchone"
    ALL = "fetchall"


def timestamp_format(timestamp: float, time_format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    时间戳转换可读时间字符串
    """
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime(time_format)


class Main:
    memos_db_path: Path = Path("./memos_prod.db")
    assets_map = {}
    relative_path: str
    prefix: str

    def __init__(self) -> None:
        args = sys.argv
        if len(args) >= 2:
            _, custom_db, *_ = args
            self.memos_db_path = Path(custom_db)

        if not Path.exists(self.memos_db_path):
            print(f"* Path {str(self.memos_db_path)} doesn't exists")
            sys.exit(0)

    def db_query(self, sql: str, fetch: Fetch = Fetch.ALL) -> Any:
        """
        数据库查询, 默认sqlite3
        """
        connect = sqlite3.connect(self.memos_db_path)  # 可以更换为其他DB
        cursor = connect.cursor()
        if fetch == Fetch.ALL:
            result = cursor.execute(sql).fetchall()
        else:
            result = cursor.execute(sql).fetchone()
        cursor.close()
        connect.close()
        return result

    def get_relative_path(self) -> None:
        """
        查询存储路径, memos默认的值为: "assets/{timestamp}_{filename}"
        """
        sql = "select value from system_setting where name = 'local-storage-path';"
        path: str = self.db_query(sql, fetch=Fetch.ONE)[0]
        self.relative_path = path.replace('"', "")
        print(f"* Relative path obtained successfully: {self.relative_path}")

    def get_content(self) -> list:
        """
        查询所有的memos、用户与附件关联关系, 其中blob数据也会查询出来, 在这里使用 assets_type 来区分附件类型, 已知的附件类型为 ["file", "blob"]
        """
        sql = """
select m.id                as memo_id,
       u.nickname          as nickname,
       m.content           as content,
       m.created_ts        as created_ts,
       r.filename          as filename,
       r.blob              as blob_data,
       r.internal_path     as file_path,
       case
           when r.blob is null then
               case
                   when r.filename is null then null
                   else
                       'file' end
           else 'blob' end as assets_type
from memo m
         left join resource r on m.id = r.memo_id
         left join user u on m.creator_id = u.id
order by m.id;
"""
        return self.db_query(sql, fetch=Fetch.ALL)

    def create_assets_map(self, data_list: list) -> None:
        """
        创建附件映射字典, 存入 self.assets_map
        """
        print(f"* Creating the assets mapping...")

        self.prefix = self.relative_path.split("/")[0]  # 获取存储前缀
        for row in data_list:
            (
                memo_id,
                nickname,
                content,
                created_ts,
                filename,
                blob_data,
                file_path,
                assets_type,
            ) = row  # 查询记录解包

            # 附件类型判断
            if assets_type == "blob":
                blob2file_dir_path = Path(f"{self.prefix}/blob2file")  # 构建写入路径
                blob2file_dir_path.mkdir(exist_ok=True, parents=True)
                blob_file_path = Path(blob2file_dir_path, f"{created_ts}_{filename}")
                with open(blob_file_path, "wb") as tmp_file:  # 写入 blob 内容
                    tmp_file.write(blob_data)
                assets_path = str(blob_file_path)  # 重构附件链接路径
            elif assets_type == "file":
                assets_path = file_path.replace("/var/opt/memos/", "")  # 使用相对路径
            else:
                assets_path = None

            if memo_id not in self.assets_map:
                self.assets_map[memo_id] = {
                    "nickname": nickname,
                    "content": content,
                    "created_ts": created_ts,
                    "filename": filename,
                    "assets_path": assets_path,
                }  # 构建字典映射
            else:
                # 多附件追加
                self.assets_map[memo_id]["filename"] += f",{filename}"
                self.assets_map[memo_id]["assets_path"] += f",{assets_path}"

        print(f"* You have {len(self.assets_map)} memos, assets mapping completed")

    def create_md_file(self) -> None:
        """
        构建 markdown 目录与文件, 并处理附件
        """
        print("* Start building the markdown file structure...")
        t = len(self.assets_map)
        n = 0
        for i in self.assets_map:  # 循环字典映射
            print(f"* {n}/{t}", end="\r")
            author = self.assets_map[i]["nickname"]
            file_timestamp = int(self.assets_map[i]["created_ts"])
            md_path = Path(f"memos2md_files/{author}")  # 使用 nickname 作为目录结构
            Path.mkdir(md_path, parents=True, exist_ok=True)

            if self.assets_map[i]["filename"] is None:  # 如果这个 memo 没有附件
                filename_list = []
                filepath_list = []
                assets_count = 0
            else:
                filename_list = self.assets_map[i]["filename"].split(",")
                filepath_list = self.assets_map[i]["assets_path"].split(",")
                assets_count = len(filename_list)

            with open(
                Path(
                    md_path,
                    f"{author}_{timestamp_format(file_timestamp, '%Y%m%d%H%M%S')}.md",
                ),
                "w",
                encoding="utf-8",
            ) as md_file:  # markdown 文件命名规则: {nickname}_{created_ts}.md
                header = f"> Original time: {timestamp_format(file_timestamp, '%Y-%m-%d %H:%M:%S')}\n\n\n"

                if you_like_it:
                    # =D
                    pass
                else:
                    by_info = f"> This file was converted by [{memos2md}]({github_url}), sourced from: {str(self.memos_db_path)}\n> \n> Conversion time: {timestamp_format(int(time.time()), '%Y-%m-%d %H:%M:%S')}\n> \n"
                    header = by_info + header

                md_file.write(header)
                md_file.write(self.assets_map[i]["content"])

                if assets_count != 0:  # 如果存在附件
                    for n in range(assets_count):
                        md_file.write(
                            f"\n![{filename_list[n]}]({filepath_list[n]})"
                        )  # 写入 markdown 图片链接, 参考: https://www.markdownguide.org/basic-syntax/#images-1

            for path in filepath_list:  # 附件拷贝整合
                if path != "":
                    path = str(path)
                    assets_dir = Path(os.path.dirname(path))
                    Path.mkdir(Path(md_path, assets_dir), exist_ok=True, parents=True)
                    dst_path = f"{md_path}/{path}"

                    shutil.copy(path, dst_path)

            n += 1

        print("\n* Conversion complete")

    def run(self):
        self.get_relative_path()
        self.create_assets_map(self.get_content())
        self.create_md_file()


if __name__ == "__main__":
    Main().run()
    pass
