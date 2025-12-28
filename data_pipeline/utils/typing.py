from typing import Type
from pydantic import BaseModel

def validate_data(data: dict, model: Type[BaseModel]) -> dict:
    """
    Validates input data against the provided Pydantic model.
    
    Args:
        data (dict): The input data to validate.
        model (BaseModel): The Pydantic model class to validate against.
        
    Returns:
        BaseModel: An instance of the model with validated data.
        
    Raises:
        ValidationError: If the data does not conform to the model.
    """
    return model.model_validate(data).model_dump(mode="json")