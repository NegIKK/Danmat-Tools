import bpy

last_helper_collection_name = ""

def Get_Scene_Collections():
    collections_list = ["Scene Collection"]
    for collection in bpy.data.collections:
        collections_list.insert(-1, collection.name)   
    return collections_list


def Get_Collection_Name_Of_Object(obj):
    # print(obj.users_collection[0].name)
    return obj.users_collection[0].name


def Create_Collection(new_collection_name, collection_parent): #работает только когда целевая колекция находится в корне, если она вложена то нет
    def traverse_tree(t):
        yield t
        for child in t.children:
            yield from traverse_tree(child)

    coll = bpy.context.scene.collection

    for c in traverse_tree(coll):
        if c.name == collection_parent: # Specify the name of you main collection here
            my_sub_coll = bpy.data.collections.new(new_collection_name)
            # Add it to the main collection
            c.children.link(my_sub_coll)


def Create_Helper_Collection(suffix):
    colletction_of_selected_obj = Get_Collection_Name_Of_Object(bpy.context.object)
    # print(colletction_of_selected_obj)

    collection_name_to_create = colletction_of_selected_obj + "_" + suffix

    all_scene_collections = Get_Scene_Collections()
    
    is_helper_exist = False
    for collection in all_scene_collections:
        if collection_name_to_create == collection:
            is_helper_exist = True

    if is_helper_exist == False:
        Create_Collection(collection_name_to_create, colletction_of_selected_obj)
    
    return(collection_name_to_create) 


def Move_To_Collection(objects_to_move, target_collection):
    for obj in objects_to_move:
        
        current_obj_collection_name = Get_Collection_Name_Of_Object(obj)
        if current_obj_collection_name != "Scene Collection":
            current_obj_collection = bpy.data.collections[current_obj_collection_name]
            current_obj_collection.objects.unlink(obj)
        else:
            bpy.context.scene.collection.objects.unlink(obj)

        bpy.data.collections[target_collection].objects.link(obj)

    # print(current_obj_collection_name)


# Add_Helper_Collection("BOOLS")
# print(Get_Collection_Name_Of_Object(bpy.context.object))
# print(Get_Scene_Collections())
# Move_To_Collection(bpy.context.selected_objects, Add_Helper_Collection("BOOL"))



# Get_Current_Collections()

