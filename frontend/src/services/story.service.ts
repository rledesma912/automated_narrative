import axios from "axios";

const CORE_API_URL = process.env.CORE_API_URL ?? "http://localhost:8010";

export interface Story {
  id: string;
  title: string;
  status: string;
  created_at: string;
  atmosfera?: string;
  protagonista?: string;
  relator?: string;
  sinopsis?: string;
  file_path?: string;
}

export interface Relato {
  id: string;
  story_template_id: string;
  title: string;
  content: string;
  status: string;
  created_at: string;
}

export const getStoryById = async (storyId: string): Promise<Story | null> => {
  try {
    const response = await axios.get<Story>(
      `${CORE_API_URL}/api/v1/stories/${storyId}`,
      { timeout: 5000 }
    );
    return response.data;
  } catch (error) {
    console.error(`Error fetching story ${storyId}:`, error);
    return null;
  }
};

export const getRelatosForStory = async (storyId: string): Promise<Relato[]> => {
  try {
    const response = await axios.get<Relato[]>(
      `${CORE_API_URL}/api/v1/story-templates/${storyId}/narratives`,
      { timeout: 5000 }
    );
    return response.data;
  } catch (error) {
    console.error(`Error fetching narratives for story ${storyId}:`, error);
    return [];
  }
};