import os
from .exceptions import log_execution, handle_exceptions


class LlamaParseService:
    def __init__(self):
        from llama_parse import LlamaParse
        self.api_key = os.getenv("LLAMACLOUD_API_KEY")
        if not self.api_key:
            raise ValueError("LLAMACLOUD_API_KEY not configured")
        self.parser = LlamaParse(result_type="markdown", api_key=self.api_key)
    @log_execution
    @handle_exceptions
    def parse(self, file: str, file_extension: str) -> str:
        """
        Parses a document file using LlamaParse and returns the content.

        Args:
            file_path (str): Path to the document file.
            file_extension (str, optional): File extension. If None, will be inferred from the file path.
            return_as_list (bool): If True, returns a list of page contents. If False, returns concatenated string.

        Returns:
            Union[str, List[str]]: The parsed content as either a concatenated string or a list of page contents.
                                  Returns empty string or empty list on error based on return_as_list parameter.
        """

        file_extractor = {file_extension: self.parser}

        # Parse the document
        from llama_index.core import SimpleDirectoryReader
        documents = SimpleDirectoryReader(
            input_files=[file],
            file_extractor=file_extractor
        ).load_data()
        
        # Extract text from all documents
        parsed_content = [doc.text for doc in documents]
        
        # Return
        return "".join(parsed_content)
            