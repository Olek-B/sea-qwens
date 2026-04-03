from shared.indexer import CodeIndexer


class PostIndexer:
    """Incrementally index changed files after a merge.

    Receives file content in the request body — the Librarian container
    never needs filesystem access to the project.
    """

    def __init__(self, neo4j, chroma):
        self.neo4j = neo4j
        self.chroma = chroma
        self.indexer = CodeIndexer()

    def index_files(self, files: list[dict]) -> dict:
        results = []
        for file_info in files:
            rel_path = file_info["path"]
            content = file_info["content"]
            language = file_info.get("language", "python")
            if content is None:
                self.neo4j.delete_file(rel_path)
                results.append({"file": rel_path, "action": "deleted"})
                continue
            try:
                result = self.indexer.index_file(rel_path, content, language)
                self.neo4j.upsert_index_result(result)
                for func in result.functions:
                    uid = f"{func.file_path}:{func.name}"
                    self.chroma.delete_by_id(uid)
                    self.chroma.add_function_embedding(
                        uid=uid, body=func.body,
                        metadata={"name": func.name, "file": func.file_path}
                    )
                for cls in result.classes:
                    uid = f"{cls.file_path}:{cls.name}"
                    self.chroma.delete_by_id(uid)
                    self.chroma.add_class_embedding(
                        uid=uid, body=cls.body,
                        metadata={"name": cls.name, "file": cls.file_path}
                    )
                results.append({
                    "file": rel_path, "action": "updated",
                    "functions": len(result.functions), "classes": len(result.classes)
                })
            except Exception as e:
                results.append({"file": rel_path, "action": "error", "error": str(e)})
        return {"total": len(files), "results": results}
